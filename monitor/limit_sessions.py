"""Persistent, password-bound cookies for the read-only public Limit listener."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from email.utils import formatdate
from http.cookies import SimpleCookie
from pathlib import Path

COOKIE = '__Host-limit_session'
VERSION = 1


def encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def decode(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


class PublicSessions:
    def __init__(self, data, clock=None):
        self.data = Path(data)
        self.clock = clock or time.time

    def configuration(self, auth):
        settings = json.loads((self.data / 'public-session.json').read_bytes())
        days = settings.get('days')
        if type(days) is not int or not 7 <= days <= 365:
            raise ValueError('Invalid public session lifetime')
        secret = (self.data / 'public-session-secret').read_bytes()
        if len(secret) != 64:
            raise ValueError('Invalid public session secret')
        # A password change (including its salt) immediately invalidates cookies.
        binding = json.dumps(['limit-public-session-v1', auth['username'], auth['salt'],
                              auth['digest']], ensure_ascii=False, separators=(',', ':')).encode()
        return days * 86400, hmac.digest(secret, binding, 'sha256')

    def issue(self, auth):
        lifetime, key = self.configuration(auth)
        now = int(self.clock())
        expiry = now + lifetime
        payload = encode(json.dumps({'v': VERSION, 'iat': now, 'exp': expiry,
                                     'n': secrets.token_urlsafe(16)}, separators=(',', ':')).encode())
        token = payload + '.' + encode(hmac.digest(key, payload.encode('ascii'), 'sha256'))
        return (f'{COOKIE}={token}; Path=/; Max-Age={lifetime}; '
                f'Expires={formatdate(expiry, usegmt=True)}; Secure; HttpOnly; SameSite=Strict')

    def verify(self, header, auth):
        if not header or len(header) > 8192:
            return False
        try:
            # Duplicate session names must not be interpreted differently by proxies.
            if sum(part.split('=', 1)[0].strip() == COOKIE for part in header.split(';')) != 1:
                return False
            jar = SimpleCookie()
            jar.load(header)
            token = jar[COOKIE].value
            if len(token) > 1024:
                return False
            payload, signature = token.split('.')
            lifetime, key = self.configuration(auth)
            actual = decode(signature)
            expected = hmac.digest(key, payload.encode('ascii'), 'sha256')
            if not hmac.compare_digest(actual, expected):
                return False
            claims = json.loads(decode(payload))
            if not isinstance(claims, dict) or set(claims) != {'v', 'iat', 'exp', 'n'}:
                return False
            if type(claims['v']) is not int or claims['v'] != VERSION:
                return False
            if type(claims['iat']) is not int or type(claims['exp']) is not int:
                return False
            if not isinstance(claims['n'], str) or len(claims['n']) != 22:
                return False
            now = int(self.clock())
            return (claims['iat'] <= now + 60 and claims['exp'] > now and
                    0 < claims['exp'] - claims['iat'] <= lifetime)
        except Exception:
            return False
