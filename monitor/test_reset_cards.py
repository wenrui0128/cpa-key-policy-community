"""Offline reset-card regressions; no upstream calls or real credentials."""
import copy
import importlib.util
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from limit_reset_cards import ResetCards, URL, count, expiry, install, normalize

NOW = 1791446400


def payload():
    return {'available_count': 3, 'credits': [
        {'id': 'private-test-id-' + str(i), 'profile_user_id': 'private-profile',
         'profile_image_url': 'https://example.invalid/test', 'reset_type': 'codex_rate_limits',
         'status': 'available', 'expires_at': value}
        for i, value in enumerate(['2026-10-22T20:54:58.046668Z',
                                  '2026-10-29T19:06:43.908161Z',
                                  '2026-11-06T23:35:32.224142Z'])]}


class MockApp:
    def __init__(self):
        self.LOCK = threading.RLock()
        self.cache = {}
        self.calls = []
        self.fail = False
        self.account = 'private-test-account'
        self.body = payload()

    def load(self, name):
        return copy.deepcopy(self.cache.get(name))

    def save(self, name, value):
        self.cache[name] = copy.deepcopy(value)

    def api(self, path, value=None):
        self.calls.append((path, value))
        if path == 'auth-files':
            return {'files': [{'provider': 'codex', 'disabled': False, 'auth_index': self.account,
                              'metadata': {'chatgpt_account_id': 'private-test-header'}},
                             {'provider': 'codex', 'disabled': True}, {'provider': 'other'}]}
        if self.fail:
            raise RuntimeError('private-token must never be in public error')
        return {'status_code': 200, 'body': json.dumps(self.body)}


class NormalizationTests(unittest.TestCase):
    def test_live_shape_and_private_fields_are_discarded(self):
        record = normalize(payload(), NOW)
        self.assertEqual(record['available_count'], 3)
        self.assertEqual(record['unknown_expiry_count'], 0)
        self.assertEqual(record['expirations'][0], {'count': 1, 'expires_at': 1792702498})
        self.assertNotIn('private', json.dumps(record))
        self.assertNotIn('profile', json.dumps(record))

    def test_group_equal_expiry_and_exclude_consumed_or_other_types(self):
        body = payload()
        body['credits'][1]['expires_at'] = body['credits'][0]['expires_at']
        body['credits'] += [{'status': 'consumed', 'reset_type': 'codex_rate_limits'},
                            {'status': 'available', 'reset_type': 'unrelated'}]
        record = normalize(body, NOW)
        self.assertEqual([b['count'] for b in record['expirations']], [2, 1])

    def test_missing_expiry_keeps_unknown_quantity(self):
        body = payload()
        body['credits'][0]['expires_at'] = 'not-a-date'
        body['available_count'] = 4
        record = normalize(body, NOW)
        self.assertEqual(record['available_count'], 4)
        self.assertEqual(record['unknown_expiry_count'], 2)
        self.assertEqual(normalize({'available_count': 0}, NOW)['available_count'], 0)
        self.assertEqual(normalize({'available_count': 3}, NOW)['unknown_expiry_count'], 3)

    def test_invalid_payloads_fail_instead_of_zero(self):
        for body in [None, [], {}, {'available_count': True}, {'available_count': -1},
                     {'available_count': 1.5}, {'available_count': 2, 'credits': payload()['credits']},
                     {'available_count': 3, 'credits': 'invalid'}, {'credits': [None]}]:
            with self.subTest(body=body), self.assertRaises((ValueError, TypeError)):
                normalize(body, NOW)
        body = payload()
        body['credits'][1]['id'] = body['credits'][0]['id']
        with self.assertRaises(ValueError):
            normalize(body, NOW)

    def test_timezone_and_numeric_validation(self):
        self.assertEqual(expiry('2026-10-23T04:54:58+08:00'), 1792702498)
        self.assertEqual(count('3'), 3)
        for value in ['2026-10-23T04:54:58', True, float('inf'), 0, 'bad']:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                expiry(value)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.app = MockApp()
        self.now = NOW
        self.monitor = ResetCards(self.app, lambda: self.now)

    def test_query_is_only_get_and_public_view_has_no_secrets(self):
        self.monitor.sync()
        view = self.monitor.view()
        self.assertTrue(view['ok'])
        self.assertEqual(view['available_count'], 3)
        self.assertEqual(self.app.calls[0], ('auth-files', None))
        path, request = self.app.calls[1]
        self.assertEqual(path, 'api-call')
        self.assertEqual(request['method'], 'GET')
        self.assertEqual(request['url'], URL)
        self.assertEqual(request['header']['Authorization'], 'Bearer $TOKEN$')
        self.assertNotIn('consume', request['url'])
        encoded = json.dumps(view)
        for private in ['account_ref', 'authIndex', 'profile', 'private', 'TOKEN', 'http']:
            self.assertNotIn(private, encoded)

    def test_failure_and_restart_keep_last_confirmed_count(self):
        self.monitor.sync()
        old = self.monitor.view()
        self.app.fail = True
        self.monitor.sync()
        view = self.monitor.view()
        self.assertFalse(view['ok'])
        self.assertEqual(view['expirations'], old['expirations'])
        self.assertEqual(view['available_count'], 3)
        self.assertNotIn('private-token', view['error'])
        restarted = ResetCards(self.app, lambda: self.now)
        self.assertEqual(restarted.view()['available_count'], 3)
        self.assertFalse(restarted.view()['ok'])

    def test_first_failure_unknown_and_malformed_response_preserves_cache(self):
        self.app.fail = True
        self.monitor.sync()
        self.assertIsNone(self.monitor.view()['available_count'])
        self.app.fail = False
        self.monitor.sync()
        self.app.body = {}
        self.monitor.sync()
        self.assertEqual(self.monitor.view()['available_count'], 3)
        self.assertFalse(self.monitor.view()['ok'])

    def test_stale_cache_and_local_expiry(self):
        self.monitor.sync()
        self.now += 301
        self.assertFalse(self.monitor.view()['ok'])
        self.now = expiry(payload()['credits'][0]['expires_at'])
        view = self.monitor.view()
        self.assertEqual(view['available_count'], 2)
        self.assertEqual(len(view['expirations']), 2)
        self.now = expiry(payload()['credits'][-1]['expires_at'])
        self.assertEqual(self.monitor.view()['available_count'], 0)

    def test_account_change_never_shows_other_account_cache(self):
        self.monitor.sync()
        self.app.account = 'changed-private-account'
        self.app.fail = True
        self.monitor.sync()
        self.assertIsNone(self.monitor.view()['available_count'])

    def test_snapshot_extension_preserves_other_fields(self):
        self.app.snapshot = lambda: {'official': {'remaining_percent': 90},
                                     'plugin': {'keys': []}, 'cycle': 'unchanged'}
        before = self.app.snapshot()
        with patch('limit_reset_cards.threading.Thread'):
            monitor = install(self.app)
        monitor.sync()
        after = self.app.snapshot()
        self.assertEqual({k: v for k, v in after.items() if k != 'reset_cards'}, before)
        self.assertEqual(after['reset_cards']['available_count'], 3)

    def test_candidate_import_and_extension_integration(self):
        candidate = str(Path(__file__).with_name('app.py'))
        spec = importlib.util.spec_from_file_location('cards_candidate', candidate)
        app = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = app
        spec.loader.exec_module(app)
        cache = {'plugin': {'keys': [], 'at': NOW}, 'cycle': {'unchanged': True}}
        with patch.object(app, 'load', lambda k: copy.deepcopy(cache.get(k))), \
             patch.object(app, 'save', lambda k, v: cache.update({k: v})), \
             patch.object(app, 'api', self.app.api), patch('limit_reset_cards.threading.Thread'):
            before = app.snapshot()
            monitor = install(app)
            monitor.sync()
            after = app.snapshot()
            self.assertEqual(after['reset_cards']['available_count'], 3)
            self.assertEqual({k: v for k, v in after.items() if k != 'reset_cards'}, before)
            self.assertTrue(hasattr(app, 'PublicHandler'))


if __name__ == '__main__':
    unittest.main()
