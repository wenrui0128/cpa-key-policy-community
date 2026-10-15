#!/usr/bin/env python3
"""Create local read-only viewer credentials; never ship them with source."""
import argparse,getpass,hashlib,json,os,secrets
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--data',default='./data');p.add_argument('--username',default='viewer');p.add_argument('--days',type=int,default=30);a=p.parse_args()
if not 7<=a.days<=365:p.error('days must be 7..365')
password=getpass.getpass('Viewer password (at least 16 characters): ')
if len(password)<16 or password!=getpass.getpass('Repeat password: '):raise SystemExit('Password too short or confirmation differs')
root=Path(a.data);root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
for name in ['loopback-auth.json','public-session.json','public-session-secret']:
 if (root/name).exists():raise SystemExit('Credential files already exist; back them up before rotation')
salt=secrets.token_hex(16);iterations=300000
values={'loopback-auth.json':json.dumps({'username':a.username,'salt':salt,'iterations':iterations,'digest':hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),iterations).hex()}).encode(),'public-session.json':json.dumps({'days':a.days}).encode(),'public-session-secret':secrets.token_bytes(64)}
for name,raw in values.items():
 with (root/name).open('xb') as f:f.write(raw)
 os.chmod(root/name,0o600)
print('Viewer credentials initialized locally. Password not printed. Keep this data directory private.')
