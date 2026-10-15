"""Read-only CPA Limit monitor. CPA is the sole accounting source."""
import json,math,os,sqlite3,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import urllib.request,urllib.error
BASE=os.getenv('CPA_BASE','http://127.0.0.1:8317')+'/v0/management/'
DATA=Path(os.getenv('DATA_DIR','/data'));KEYFILE=Path(os.getenv('KEY_FILE','/run/secrets/cpa_management_key'))
BIND=os.getenv('BIND','127.0.0.1');PORT=int(os.getenv('PORT','18765'))
LOCK=threading.RLock()
CYCLE_SYNC_ENABLED=os.getenv('SYNC_OFFICIAL_CYCLE','false').lower()=='true'
STATUS={'plugin_ok':False,'official_ok':False,'plugin_error':'等待首次同步','official_error':'等待首次同步','cycle_ok':not CYCLE_SYNC_ENABLED,'cycle_error':'等待周期同步' if CYCLE_SYNC_ENABLED else ''}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def api(path,payload=None,method=None):
    verb=method or ('POST' if payload is not None else 'GET')
    if verb != 'GET' and not (verb == 'POST' and path in ('api-call','plugins/cpa-key-policy/cycle/sync')):
        raise ValueError('Read-only monitor: operation not permitted')
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(BASE+path,data=data,method=method,headers={'Authorization':'Bearer '+KEYFILE.read_text().strip(),'Content-Type':'application/json'})
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with op.open(req,timeout=35) as r:return json.load(r)
def db():
    c=sqlite3.connect(DATA/'cache.sqlite');c.execute('PRAGMA synchronous=FULL');return c
def load(name):
    with db() as c:r=c.execute('SELECT value FROM cache WHERE name=?',(name,)).fetchone()
    return json.loads(r[0]) if r else None
def save(name,value):
    with db() as c:c.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(name,json.dumps(value)))
def clean_key(k):
    return {**{f:k.get(f) for f in ['id','name','enabled','daily_limit_usd','weekly_limit_usd']},
       'usage':{f:k.get('usage',{}).get(f) for f in ['daily_usd','weekly_usd','daily_reset_at','weekly_reset_at','weekly_call_count','weekly_cache_read_tokens','weekly_input_tokens','weekly_output_tokens']},
       'unpriced_models':[m.get('alias') for m in k.get('models',[]) if not any(m.get(f,0) for f in ['input_price_per_million','output_price_per_million','per_call_usd'])]}
def sync_plugin():
    try:
        keys=api('plugins/cpa-key-policy/keys')['keys']
        clean=[clean_key(k) for k in keys]
        with LOCK:save('plugin',{'keys':clean,'at':time.time()});STATUS.update(plugin_ok=True,plugin_error='')
    except Exception:
        with LOCK:STATUS.update(plugin_ok=False,plugin_error='插件查询失败，显示上次统计')
def normalize_quota(body,now):
    windows=body.get('rate_limit',{})
    matches=[x for x in [windows.get('primary_window'),windows.get('secondary_window')] if isinstance(x,dict) and x.get('limit_window_seconds')==604800]
    if len(matches)!=1:raise ValueError('weekly window not uniquely identified')
    w=matches[0];used=w.get('used_percent');end=w.get('reset_at')
    if isinstance(used,bool) or not isinstance(used,(int,float)) or not math.isfinite(used) or not 0<=used<=100:raise ValueError('bad percent')
    if isinstance(end,bool) or not isinstance(end,(int,float)) or not math.isfinite(end) or not now<end<=now+8*86400:raise ValueError('bad end')
    return {'used_percent':used,'remaining_percent':100-used,'reset_at':end,'at':now}
def accept_quota(old,new,pending):
    if old:
        if new['reset_at']<old['reset_at']:return old,None,'CPA 周期回退，保留最后确认额度'
        if new['reset_at']==old['reset_at'] and new['used_percent']<old['used_percent']:return old,None,'同周期用量回退，保留最后确认额度'
        if new['reset_at']>old['reset_at']:
            if not pending or pending['reset_at']!=new['reset_at'] or new['at']-pending['at']<30:
                return old,new,'检测到新周期，等待再次确认；未重置个人消费'
    return new,None,''
def sync_official():
    try:
        files=[f for f in api('auth-files').get('files',[]) if f.get('provider')=='codex' and not f.get('disabled')]
        if len(files)!=1:raise ValueError('requires exactly one Codex account')
        f=files[0];header={'Authorization':'Bearer $TOKEN$','Content-Type':'application/json','User-Agent':'codex-tui/0.149.1'}
        for obj in [f,f.get('metadata',{}),f.get('attributes',{})]:
            if isinstance(obj,dict) and obj.get('chatgpt_account_id'):header['Chatgpt-Account-Id']=obj['chatgpt_account_id'];break
        result=api('api-call',{'authIndex':f['auth_index'],'method':'GET','url':'https://chatgpt.com/backend-api/wham/usage','header':header})
        if result.get('status_code')!=200:raise ValueError('quota query failed')
        body=result.get('body');body=json.loads(body) if isinstance(body,str) else body
        new=normalize_quota(body,time.time());new['account_ref']=f['auth_index']
        with LOCK:
            old=load('official')
            if old and old.get('account_ref')!=new['account_ref']:raise ValueError('account changed; manual review required')
            accepted,pending,error=accept_quota(old,new,load('pending'))
            save('official',accepted);save('pending',pending);STATUS.update(official_ok=not error,official_error=error)
        if not error and CYCLE_SYNC_ENABLED:
            try:
                result=api('plugins/cpa-key-policy/cycle/sync',{'account':accepted['account_ref'],'start':int(accepted['reset_at'])-604800,'end':int(accepted['reset_at'])})
                with LOCK:save('cycle',result);STATUS.update(cycle_ok=True,cycle_error='')
            except Exception:
                with LOCK:STATUS.update(cycle_ok=False,cycle_error='个人周期同步未确认，保留账本并等待重试')
    except Exception:
        with LOCK:STATUS.update(official_ok=False,official_error='官方查询失败或数据无效，保留最后确认额度')
def snapshot():
    if os.getenv('DEMO_MODE','false').lower()=='true':
        data=json.loads((Path(__file__).parent/'examples/demo-state.json').read_text())
        delta=time.time()-data['official']['at']
        def shift(value):
            if isinstance(value,dict):return {k:v+delta if k in ('at','reset_at','expires_at','weekly_reset_at','daily_reset_at') and isinstance(v,(int,float)) else shift(v) for k,v in value.items()}
            if isinstance(value,list):return [shift(v) for v in value]
            return value
        return shift(data)
    with LOCK:
        official=load('official');p=load('plugin') or {'keys':[],'at':None};status=dict(STATUS)
        if official:
            official={k:v for k,v in official.items() if k!='account_ref'}
            if official['reset_at']<=time.time():status.update(official_ok=False,official_error='官方缓存周期已过期，等待有效确认；未重置个人消费')
            elif time.time()-official['at']>300:status.update(official_ok=False,official_error='官方数据已超过 5 分钟，保留最后确认额度')
        if p['at'] and time.time()-p['at']>60:status.update(plugin_ok=False,plugin_error='个人统计暂未刷新')
        return {'official':official,'plugin':p,'status':status,'mode':'monitor','cycle_reset_enabled':CYCLE_SYNC_ENABLED,'display':{'estimated_total':float(os.getenv('ESTIMATED_TOTAL','1000')),'time_zone':os.getenv('DISPLAY_TIMEZONE','UTC')}}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,kind='application/json; charset=utf-8'):
        raw=json.dumps(body,ensure_ascii=False).encode() if isinstance(body,dict) else body
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def valid_host(self):
        allowed={f'{BIND}:{PORT}',f'127.0.0.1:{PORT}','localhost:'+str(PORT)}
        allowed.update(h.strip() for h in os.getenv('ALLOWED_HOSTS','').split(',') if h.strip())
        return self.headers.get('Host') in allowed
    def do_GET(self):
        if not self.valid_host():return self.send(403,{'error':'Invalid host'})
        if self.path=='/api/state':return self.send(200,snapshot())
        if self.path=='/health':return self.send(200,{'ok':True})
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if self.path not in files:return self.send(404,{'error':'Not found'})
        name,kind=files[self.path];self.send(200,(Path(__file__).parent/name).read_bytes(),kind)
    def do_POST(self):
        self.send(405,{'error':'只读监控面板，不提供设置或写入接口'})
    do_PUT=do_POST
    do_PATCH=do_POST
    do_DELETE=do_POST

# Authentication applies to every listener, including private networks.
import base64,hashlib,hmac,collections
from limit_sessions import PublicSessions
PUBLIC_SESSIONS=PublicSessions(DATA)
PUBLIC_AUTH_LOCK=threading.Lock()
PUBLIC_AUTH_FAILURES=collections.deque()
class PublicHandler(Handler):
    def version_string(self):return 'Limit'
    def end_headers(self):
        cookie=getattr(self,'_public_session_cookie',None)
        if cookie:
            self.send_header('Set-Cookie',cookie)
            self._public_session_cookie=None
        super().end_headers()
    def authorized(self):
        self._public_session_cookie=None
        try:cfg=json.loads((DATA/'loopback-auth.json').read_text())
        except Exception:cfg=None
        # Existing sessions remain usable even when failed password attempts
        # have temporarily exhausted the global password-attempt allowance.
        if cfg and PUBLIC_SESSIONS.verify(self.headers.get('Cookie',''),cfg):return True
        now=time.monotonic()
        with PUBLIC_AUTH_LOCK:
            while PUBLIC_AUTH_FAILURES and now-PUBLIC_AUTH_FAILURES[0]>60:PUBLIC_AUTH_FAILURES.popleft()
            if len(PUBLIC_AUTH_FAILURES)>=20:
                self.send(429,{'error':'Authentication temporarily limited'});return False
        try:
            if cfg is None:raise ValueError('configuration')
            header=self.headers.get('Authorization','')
            if len(header)>2048 or not header.startswith('Basic '):raise ValueError('missing')
            user,password=base64.b64decode(header[6:],validate=True).decode().split(':',1)
            digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(cfg['salt']),cfg['iterations']).hex()
            if not (hmac.compare_digest(user,cfg['username']) and hmac.compare_digest(digest,cfg['digest'])):raise ValueError('invalid')
            self._public_session_cookie=PUBLIC_SESSIONS.issue(cfg)
            return True
        except Exception:
            # Missing credentials are challenged without consuming failure quota.
            if self.headers.get('Authorization'):
                with PUBLIC_AUTH_LOCK:PUBLIC_AUTH_FAILURES.append(now)
            body=b'{"error":"Authentication required"}'
            self.send_response(401)
            self.send_header('WWW-Authenticate','Basic realm="Limit", charset="UTF-8"')
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)
            return False
    def do_GET(self):
        if self.path=='/health':return self.send(200,{'ok':True})
        if self.authorized():super().do_GET()
    def do_POST(self):
        if self.authorized():super().do_POST()
    def do_HEAD(self):
        if self.authorized():
            self.send_response(405);self.send_header('Content-Length','0');self.send_header('Cache-Control','no-store');self.end_headers()
    do_PUT=do_POST
    do_PATCH=do_POST
    do_DELETE=do_POST

def loop():
    last=0
    while True:
        sync_plugin()
        if time.time()-last>=120:sync_official();last=time.time()
        time.sleep(15)
def main():
    DATA.mkdir(parents=True,exist_ok=True)
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS cache(name TEXT PRIMARY KEY,value TEXT NOT NULL)')

    if os.getenv('DEMO_MODE','false').lower()!='true':
        threading.Thread(target=loop,daemon=True).start()
        import sys
        from limit_reset_cards import install
        install(sys.modules[__name__])
    # All exposed routes require authentication; only one sync worker runs.
    # Container interfaces may bind broadly; publish only on host loopback.
    addresses=[BIND]
    servers=[]
    for address in addresses:
        while True:
            try:server=ThreadingHTTPServer((address,PORT),PublicHandler);break
            except OSError:time.sleep(5)
        servers.append(server)
        threading.Thread(target=server.serve_forever,daemon=True).start()
    threading.Event().wait()
if __name__=='__main__':main()
