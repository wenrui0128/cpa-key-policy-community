"""HTTP regressions for durable login, revocation and public data protection."""
import base64
import hashlib
import http.client
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from limit_sessions import COOKIE, PublicSessions


def authentication(password='test-only-password', salt='ab' * 16):
    return {'username': 'test-viewer', 'salt': salt, 'iterations': 1000,
            'digest': hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 1000).hex()}


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        (self.data / 'public-session-secret').write_bytes(os.urandom(64))
        (self.data / 'public-session.json').write_text('{"days":90}')
        self.clock = 1800000000
        self.auth = authentication()
        self.sessions = PublicSessions(self.data, lambda: self.clock)
        self.cookie = self.sessions.issue(self.auth).split(';', 1)[0]

    def test_restart_retains_session_and_cookie_is_persistent(self):
        restarted = PublicSessions(self.data, lambda: self.clock + 80 * 86400)
        self.assertTrue(restarted.verify(self.cookie, self.auth))
        header = self.sessions.issue(self.auth)
        for flag in ['Path=/', 'Max-Age=7776000', 'Expires=', 'Secure', 'HttpOnly', 'SameSite=Strict']:
            self.assertIn(flag, header)
        self.assertNotIn('Domain=', header)
        self.assertNotIn('test-only-password', header)
        self.assertNotIn('test-viewer', header)

    def test_expiry_is_enforced_server_side(self):
        self.clock += 90 * 86400
        self.assertFalse(self.sessions.verify(self.cookie, self.auth))

    def test_changed_password_or_username_revokes_previous_session(self):
        self.assertFalse(self.sessions.verify(self.cookie, authentication('new-test-password', 'cd' * 16)))
        self.assertFalse(self.sessions.verify(self.cookie, {**self.auth, 'username': 'other-viewer'}))

    def test_rotated_secret_revokes_session(self):
        (self.data / 'public-session-secret').write_bytes(os.urandom(64))
        self.assertFalse(self.sessions.verify(self.cookie, self.auth))

    def test_tampered_malformed_duplicate_and_oversized_tokens_fail_closed(self):
        for cookie in [self.cookie + 'x', self.cookie.replace('=', '=x', 1), 'garbage',
                       self.cookie + '; ' + self.cookie, COOKIE + '=bad.token', COOKIE + '=' + 'a' * 9000]:
            self.assertFalse(self.sessions.verify(cookie, self.auth), cookie[:30])

    def test_shorter_configuration_and_corrupt_secret_fail_closed(self):
        (self.data / 'public-session.json').write_text('{"days":30}')
        self.assertFalse(self.sessions.verify(self.cookie, self.auth))
        (self.data / 'public-session-secret').write_bytes(b'bad')
        self.assertFalse(self.sessions.verify(self.cookie, self.auth))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / 'data'
        self.data.mkdir()
        self.auth = authentication()
        (self.data / 'loopback-auth.json').write_text(json.dumps(self.auth))
        (self.data / 'public-session-secret').write_bytes(os.urandom(64))
        (self.data / 'public-session.json').write_text('{"days":90}')
        supplied = os.getenv('LIMIT_SESSION_TEST_APP')
        if supplied:
            raw = Path(supplied).read_bytes()
        else:
            raw = (HERE / 'app.py').read_bytes()
        candidate = root / 'app.py'
        candidate.write_bytes(raw)
        for name in ['index.html', 'app.js', 'style.css']:
            (root / name).write_text('synthetic public fixture')
        spec = importlib.util.spec_from_file_location('session_http_app', candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.DATA = self.data
        module.PUBLIC_SESSIONS = PublicSessions(self.data)
        # No sync worker is started and no CPA or upstream request is made.
        module.snapshot = lambda: {'plugin': {'keys': [{'id': 'synthetic-key'}]}}
        self.module = module
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), module.PublicHandler)
        module.PORT = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path='/', basic=None, cookie=None, method='GET'):
        headers = {}
        if basic is not None:
            headers['Authorization'] = 'Basic ' + base64.b64encode(('test-viewer:' + basic).encode()).decode()
        if cookie:
            headers['Cookie'] = cookie
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def login(self):
        status, headers, _ = self.request(basic='test-only-password')
        self.assertEqual(status, 200)
        return headers['Set-Cookie'].split(';', 1)[0]

    def test_basic_login_sets_persistent_cookie_and_cookie_alone_reads_all_routes(self):
        cookie = self.login()
        with patch.object(self.module.hashlib, 'pbkdf2_hmac', side_effect=AssertionError('rehashed password')):
            for route in ['/', '/api/state', '/app.js', '/style.css', '/health']:
                status, headers, _ = self.request(route, cookie=cookie)
                self.assertEqual(status, 200)
                self.assertNotIn('Set-Cookie', headers)

    def test_anonymous_and_invalid_login_reveal_no_monitor_data(self):
        for route in ['/', '/api/state', '/app.js', '/style.css', '/data/public-session-secret', '/api/state?x=1']:
            for credentials in [{}, {'basic': 'wrong-test-password'}, {'cookie': COOKIE + '=fake.token'}]:
                status, headers, body = self.request(route, **credentials)
                self.assertEqual(status, 401)
                self.assertIn('Basic realm=', headers['WWW-Authenticate'])
                self.assertNotIn(b'synthetic-key', body)
                self.assertNotIn('Set-Cookie', headers)

    def test_cookie_cannot_read_secret_files_or_mutate_the_monitor(self):
        cookie = self.login()
        self.assertEqual(self.request('/data/public-session-secret', cookie=cookie)[0], 404)
        for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            self.assertEqual(self.request('/api/state', cookie=cookie, method=method)[0], 405)

    def test_password_change_revokes_cookie_without_restart(self):
        cookie = self.login()
        (self.data / 'loopback-auth.json').write_text(json.dumps(authentication('new-test-password', 'cd' * 16)))
        self.assertEqual(self.request('/api/state', cookie=cookie)[0], 401)
        self.assertEqual(self.request('/api/state', basic='test-only-password')[0], 401)
        self.assertEqual(self.request('/api/state', basic='new-test-password')[0], 200)

    def test_established_cookie_survives_failed_password_rate_limit(self):
        cookie = self.login()
        for _ in range(20):
            self.request(basic='wrong-test-password')
        self.assertEqual(self.request()[0], 429)
        self.assertEqual(self.request('/api/state', cookie=cookie)[0], 200)

    def test_missing_session_secret_does_not_admit_a_password_request(self):
        (self.data / 'public-session-secret').unlink()
        self.assertEqual(self.request(basic='test-only-password')[0], 401)

    def test_base_handler_rejects_writes(self):
        handler = object.__new__(self.module.Handler)
        with patch.object(handler, 'send') as send:
            handler.do_POST()
            self.assertEqual(send.call_args.args[0], 405)
        self.assertNotIn('authorized', self.module.Handler.__dict__)


if __name__ == '__main__':
    unittest.main()
