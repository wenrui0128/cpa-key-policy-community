#!/usr/bin/env python3
"""Validate a built monitor image with disposable credentials and demo data."""
import base64,hashlib,json,os,secrets,socket,subprocess,tempfile,time,urllib.request,urllib.error
from pathlib import Path
IMAGE=os.getenv('MONITOR_TEST_IMAGE','quota-monitor:test')
def docker(*args):return subprocess.check_output(['docker',*map(str,args)],stderr=subprocess.STDOUT).decode()
def run():
 name='quota-monitor-test-'+secrets.token_hex(5)
 with tempfile.TemporaryDirectory(prefix='quota-monitor-test-') as tmp:
  root=Path(tmp);data=root/'data';data.mkdir();secret=secrets.token_urlsafe(32);salt=secrets.token_hex(16)
  auth={'username':'viewer','salt':salt,'iterations':300000,'digest':hashlib.pbkdf2_hmac('sha256',secret.encode(),bytes.fromhex(salt),300000).hex()}
  for key,value in {'loopback-auth.json':json.dumps(auth).encode(),'public-session.json':b'{"days":30}','public-session-secret':secrets.token_bytes(64)}.items():
   p=data/key;p.write_bytes(value);p.chmod(0o600)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  try:
   docker('run','--rm','--network','none','--user','0','-v',f'{data}:/data', '--entrypoint','sh',IMAGE,'-c','chown -R 10001:10001 /data; chmod 700 /data')
   docker('run','-d','--name',name,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--tmpfs','/tmp:rw,noexec,nosuid,size=16m','-p',f'127.0.0.1:{port}:18765','-v',f'{data}:/data','-e','DEMO_MODE=true','-e',f'ALLOWED_HOSTS=127.0.0.1:{port}',IMAGE)
   base=f'http://127.0.0.1:{port}';op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   def get(route,headers=None):
    try:
     with op.open(urllib.request.Request(base+route,headers=headers or {}),timeout=3) as r:return r.status,r.read(),r.headers
    except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
   for _ in range(50):
    try:
     if get('/health')[0]==200:break
    except OSError:pass
    time.sleep(.1)
   else:raise AssertionError('Monitor did not become ready')
   assert json.loads(get('/health')[1])=={'ok':True}
   assert get('/api/state')[0]==401 and get('/')[0]==401
   login={'Authorization':'Basic '+base64.b64encode(('viewer:'+secret).encode()).decode()}
   status,raw,headers=get('/api/state',login);assert status==200 and len(json.loads(raw)['plugin']['keys'])==6
   assert secret.encode() not in raw and b'account_ref' not in raw
   assert all(x in headers['Set-Cookie'] for x in ['Secure','HttpOnly','SameSite=Strict'])
   assert get('/api/state',{'Host':'other.example.invalid',**login})[0]==403
   assert get('/public-session-secret',login)[0]==404
   info=json.loads(docker('inspect',name))[0];assert info['Config']['User']=='10001:10001' and info['HostConfig']['ReadonlyRootfs']
   print(json.dumps({'demo_data':True,'checks':['nonroot-runtime','readonly-rootfs','anonymous-health-minimal','anonymous-business-401','authenticated-state-200','secure-cookie','host-allowlist','secret-file-404']},indent=2))
  finally:
   subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   subprocess.run(['docker','run','--rm','--network','none','--user','0','-v',f'{root}:/cleanup','--entrypoint','sh',IMAGE,'-c','rm -rf /cleanup/data'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__':run()
