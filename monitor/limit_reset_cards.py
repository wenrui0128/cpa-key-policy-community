"""Read-only reset-credit monitor. Only sanitized counts and expiry times leave it."""
import json
import math
import threading
import time
from collections import Counter
from datetime import datetime

URL = 'https://chatgpt.com/backend-api/wham/rate-limit-reset-credits'
INTERVAL = 120
MAX_AGE = 300


def count(value):
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    if type(value) is not int or not 0 <= value <= 1000000:
        raise ValueError('Invalid reset-credit count')
    return value


def expiry(value):
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Missing expiry timezone')
        value = parsed.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid expiry timestamp')
    if not 946684800 <= value <= 4102444800:
        raise ValueError('Expiry timestamp out of range')
    return int(value)


def normalize(body, now):
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        raise ValueError('Invalid reset-credit payload')
    credits = body.get('credits')
    available = body.get('available_count', body.get('availableCount'))
    if available is None and not isinstance(credits, list):
        raise ValueError('No reset-credit fields')
    if credits is not None and not isinstance(credits, list):
        raise ValueError('Invalid reset-credit details')
    entries = []
    seen = set()
    for credit in credits or []:
        if not isinstance(credit, dict):
            raise ValueError('Invalid reset-credit entry')
        if credit.get('reset_type', credit.get('resetType')) != 'codex_rate_limits' or credit.get('status') != 'available':
            continue
        identifier = credit.get('id')
        if identifier:
            if not isinstance(identifier, str) or identifier in seen:
                raise ValueError('Invalid or duplicate reset-credit identifier')
            seen.add(identifier)
        try:
            expires = expiry(credit.get('expires_at', credit.get('expiresAt')))
        except (ValueError, TypeError, OverflowError):
            expires = None
        entries.append(expires)
    available = len(entries) if available is None else count(available)
    if available < len(entries):
        raise ValueError('Reset-credit count conflicts with details')
    groups = Counter(value for value in entries if value is not None)
    return {'available_count': available,
            'expirations': [{'count': groups[value], 'expires_at': value} for value in sorted(groups)],
            'unknown_expiry_count': available - sum(groups.values()), 'at': int(now)}


class ResetCards:
    def __init__(self, app, clock=None):
        self.app = app
        self.clock = clock or time.time
        self.ok = False
        self.error = '等待重置卡首次查询'

    def sync(self):
        try:
            files = [f for f in self.app.api('auth-files').get('files', [])
                     if f.get('provider') == 'codex' and not f.get('disabled')]
            if len(files) != 1:
                raise ValueError('Requires one Codex account')
            account = files[0]
            headers = {'Authorization': 'Bearer $TOKEN$', 'Content-Type': 'application/json',
                       'User-Agent': 'codex-tui/0.149.1', 'Accept': 'application/json',
                       'OpenAI-Beta': 'codex-1', 'Originator': 'Codex Desktop'}
            for obj in [account, account.get('metadata', {}), account.get('attributes', {})]:
                if isinstance(obj, dict) and obj.get('chatgpt_account_id'):
                    headers['Chatgpt-Account-Id'] = obj['chatgpt_account_id']
                    break
            with self.app.LOCK:
                old = self.app.load('reset_cards')
                if old and old.get('account_ref') != account['auth_index']:
                    self.app.save('reset_cards', None)
            result = self.app.api('api-call', {'authIndex': account['auth_index'], 'method': 'GET',
                                             'url': URL, 'header': headers})
            if result.get('status_code') != 200:
                raise ValueError('Reset-credit query failed')
            record = normalize(result.get('body'), self.clock())
            record['account_ref'] = account['auth_index']
            with self.app.LOCK:
                self.app.save('reset_cards', record)
                self.ok, self.error = True, ''
        except Exception:
            with self.app.LOCK:
                self.ok = False
                self.error = ('重置卡查询失败，保留上次确认数据' if self.app.load('reset_cards')
                              else '重置卡查询失败，等待有效数据')

    def view(self):
        with self.app.LOCK:
            record = self.app.load('reset_cards')
            if not record:
                return {'available_count': None, 'expirations': [], 'unknown_expiry_count': None,
                        'at': None, 'ok': False, 'error': self.error}
            now = self.clock()
            live, expired = [], 0
            for batch in record['expirations']:
                if batch['expires_at'] <= now:
                    expired += batch['count']
                else:
                    live.append({'count': batch['count'], 'expires_at': batch['expires_at']})
            fresh = now - record['at'] <= MAX_AGE
            return {'available_count': max(0, record['available_count'] - expired),
                    'expirations': live, 'unknown_expiry_count': record['unknown_expiry_count'],
                    'at': record['at'], 'ok': self.ok and fresh,
                    'error': self.error if not self.ok else '' if fresh else '重置卡数据超过 5 分钟，显示上次确认值'}

    def loop(self):
        while True:
            self.sync()
            time.sleep(INTERVAL)


def install(app):
    """Extend snapshot without changing existing quota/ledger worker functions."""
    monitor = ResetCards(app)
    original = app.snapshot

    def snapshot():
        data = original()
        data['reset_cards'] = monitor.view()
        return data

    app.snapshot = snapshot
    threading.Thread(target=monitor.loop, daemon=True).start()
    return monitor
