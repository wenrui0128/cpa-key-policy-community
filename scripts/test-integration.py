#!/usr/bin/env python3
"""Offline CPA integration. Requires Docker; never contacts an upstream account.
Creates an dedicated Docker network, loopback-only port and temporary synthetic
ledger. Removes its own containers/network on completion. Does not read host
CPA configuration. Set CPA_TEST_IMAGE to an already available CPA image.
"""
import base64, datetime, hashlib, importlib.util, json, os, secrets, socket
import subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
IMAGE=os.getenv('CPA_TEST_IMAGE','eceasy/cli-proxy-api:v8.0.24')
def docker(*args):
    result=subprocess.run(['docker',*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if result.returncode:raise RuntimeError('Docker test operation failed: '+result.stdout[-1500:])
    return result.stdout
def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat().replace('+00:00','Z')
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def run():
    library=ROOT/'dist/cpa-key-policy_linux_amd64.so'
    if not library.exists():raise SystemExit('Build the Linux amd64 shared library first')
    tag='quota-integration-'+secrets.token_hex(5);port=free_port();secret=secrets.token_urlsafe(32)
    report={'cpa_image':'8.0.24','plugin_version':'0.5.1-community.2','inference_calls':0,'upstream_accounts':0,'official_responses':'mocked','checks':[]}
    with tempfile.TemporaryDirectory(prefix='quota-integration-') as tmp:
        root=Path(tmp);(root/'auth').mkdir();(root/'plugins').mkdir()
        # Stop CPA before removing temporary files even when a test fails.
        try:
            now=int(time.time());initial={'account':'synthetic-account','start':now-3600,'end':now-3600+604800}
            state={'version':1,'keys':[],'usage':{},'updated_at':iso(now)}
            demo=json.loads((ROOT/'monitor/examples/demo-state.json').read_text())
            for k in demo['plugin']['keys']:
                identifier=k['id'];cost=k['usage']['weekly_usd'];client=secrets.token_urlsafe(32)
                state['keys'].append({'id':identifier,'name':k['name'],'enabled':True,'weekly_limit_usd':k['weekly_limit_usd'],'key_hash':'sha256:'+hashlib.sha256(client.encode()).hexdigest(),'models':[{'alias':'demo','provider':'codex','target_model':'demo','input_price_per_million':1}]})
                state['usage'][identifier]={'daily':{'total_usd':cost/10,'window_start':iso(now-now%86400)},'weekly':{'total_usd':cost,'window_start':iso(now-3600)},'cycle_events':[{'at':iso(now-600),'alias':'demo','amount':cost-1},{'at':iso(now-30),'alias':'demo','amount':1}]}
            ledger=root/'state.json';ledger.write_text(json.dumps(state));ledger.chmod(0o600)
            cfg=root/'config.yaml';cfg.write_text(f'''config-version: 8
server:
  host: "0.0.0.0"
  port: 8317
oauth:
  auth-dir: /test/auth
management:
  allow-remote: true
  secret-key: "{secret}"
  disable-control-panel: true
plugins:
  enabled: true
  dir: /test/plugins
  configs:
    cpa-key-policy:
      enabled: true
      priority: 10
      state_file: /test/state.json
''');cfg.chmod(0o600)
            import shutil;shutil.copy2(library,root/'plugins/cpa-key-policy-v0.5.1-community.2.so')
            docker('network','create',tag)
            docker('run','-d','--name',tag,'--network',tag,'-p',f'127.0.0.1:{port}:8317','-v',f'{root}:/test',IMAGE,'./CLIProxyAPI','-config','/test/config.yaml')
            base=f'http://127.0.0.1:{port}'
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def request(path,payload=None,authenticated=True):
                headers={'Content-Type':'application/json'}
                if authenticated:headers['Authorization']='Bearer '+secret
                req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
                try:
                    with opener.open(req,timeout=10) as r:return r.status,r.read()
                except urllib.error.HTTPError as e:return e.code,e.read()
            prefix='/v0/management/plugins/cpa-key-policy/'
            for _ in range(40):
                try:
                    if request(prefix+'status')[0]==200:break
                except (OSError,urllib.error.URLError):pass
                time.sleep(.5)
            else:
                logs=docker('logs',tag).replace(secret,'[REDACTED]')
                raise AssertionError('Isolated CPA plugin not ready: '+logs[-6000:])
            assert request(prefix+'keys',authenticated=False)[0]==401
            assert request('/v0/resource/plugins/cpa-key-policy/index.html',authenticated=False)[0]==200
            metadata=json.loads(request('/v0/management/plugins')[1])['plugins']
            assert any(x['id']=='cpa-key-policy' and x['metadata']['version']=='0.5.1-community.2' for x in metadata)
            report['checks']+=['plugin-loaded','anonymous-management-401','embedded-ui-200']
            def keys():return json.loads(request(prefix+'keys')[1])['keys']
            before={k['id']:k['usage']['weekly_usd'] for k in keys()}
            assert len(before)==6 and sum(before.values())>0
            assert request(prefix+'cycle/sync',initial)[0]==200
            assert {k['id']:k['usage']['weekly_usd'] for k in keys()}==before
            assert request(prefix+'cycle/sync',initial)[0]==200
            next_cycle={**initial,'start':now-60,'end':now-60+604800}
            assert request(prefix+'cycle/sync',next_cycle)[0]==200
            assert all(k['usage']['weekly_usd']==1 for k in keys())
            assert request(prefix+'cycle/sync',initial)[0]==409
            assert request(prefix+'cycle/sync',{**next_cycle,'account':'different-account'})[0]==409
            assert request(prefix+'keys',{'id':'new-synthetic','name':'New synthetic key','weekly_limit_usd':10,'models':[{'alias':'demo','provider':'codex','target_model':'demo'}]})[0]==201
            new=next(k for k in keys() if k['id']=='new-synthetic')
            assert int(datetime.datetime.fromisoformat(new['usage']['weekly_reset_at'].replace('Z','+00:00')).timestamp())==next_cycle['end']
            report['checks']+=['adoption-preserves-spend','idempotent-cycle','reset-replays-post-boundary','rollback-409','account-change-409','new-key-inherits-cycle']
            # Exercise the real adapter with official endpoint responses mocked.
            data=root/'monitor';data.mkdir();keyfile=root/'management-secret';keyfile.write_text(secret)
            with patch.dict(os.environ,{'CPA_BASE':base,'DATA_DIR':str(data),'KEY_FILE':str(keyfile),'SYNC_OFFICIAL_CYCLE':'true','DEMO_MODE':'false'}):
                sys.path.insert(0,str(ROOT/'monitor'))
                spec=importlib.util.spec_from_file_location('integration_monitor',ROOT/'monitor/app.py');app=importlib.util.module_from_spec(spec);sys.modules[spec.name]=app;spec.loader.exec_module(app)
                with app.db() as db:db.execute('CREATE TABLE cache(name TEXT PRIMARY KEY,value TEXT NOT NULL)')
                app.sync_plugin();assert app.STATUS['plugin_ok']
                real_api=app.api
                def fake_official(path,payload=None,method=None):
                    if path=='auth-files':return {'files':[{'provider':'codex','auth_index':'synthetic-account','disabled':False}]}
                    if path=='api-call':return {'status_code':200,'body':{'rate_limit':{'primary_window':{'limit_window_seconds':604800,'used_percent':38,'reset_at':next_cycle['end']}}}}
                    return real_api(path,payload,method)
                with patch.object(app,'api',fake_official):app.sync_official()
                assert app.STATUS['official_ok'] and app.STATUS['cycle_ok']
                view=app.snapshot();encoded=json.dumps(view)
                assert 'synthetic-account' not in encoded and 'key_hash' not in encoded and 'key_preview' not in encoded and 'cycle_history' not in encoded and secret not in encoded
                saved=view['official']
                with patch.object(app,'api',side_effect=RuntimeError('credential detail not returned')):app.sync_official()
                assert app.snapshot()['official']==saved and not app.STATUS['official_ok']
                report['checks']+=['live-plugin-adapter','mock-official-cycle-sync','snapshot-private-fields-removed','failure-keeps-confirmed-quota']
            # Optional screenshots while the isolated CPA remains alive. Pass
            # temporary credentials in environment; never write them to output.
            browser=os.getenv('BROWSER_QA_SCRIPT')
            if browser:
                env={**os.environ,'CPA_QA_BASE':base,'CPA_QA_SECRET':secret}
                subprocess.run(['node',browser],env=env,check=True)
            docker('restart',tag)
            time.sleep(2)
            assert request(prefix+'status')[0]==200 and all(k['usage']['weekly_usd']==1 for k in keys() if k['id']!='new-synthetic')
            report['checks'].append('container-restart-retains-ledger')
        finally:
            subprocess.run(['docker','rm','-f',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['docker','network','rm',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            # Root-owned disposable state is deleted inside a helper mounted
            # only to this test directory; unrelated paths are not mounted.
            subprocess.run(['docker','run','--rm','--network','none','-v',f'{root}:/test','--entrypoint','sh',IMAGE,'-c','rm -rf /test/*'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(json.dumps(report,indent=2))
if __name__=='__main__':run()
