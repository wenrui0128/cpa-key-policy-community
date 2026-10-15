#!/usr/bin/env python3
"""Fail closed on credentials, personal paths, private IPs or unreviewed URLs.
This supplements a dedicated secret scanner; it is not a substitute for review.
"""
import ipaddress,json,pathlib,re,struct,sys,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent.parent
SKIP={'node_modules','.git','.gocache','.gomodcache','__pycache__'}
HOSTS={'localhost','127.0.0.1','0.0.0.0','::1','github.com','raw.githubusercontent.com','registry.npmjs.org','opencollective.com','tidelift.com','www.w3.org','reactjs.org','react.dev','reactrouter.com','go.dev','nodejs.org','docs.github.com','proxy.golang.org','sum.golang.org','vuln.go.dev','gopkg.in','chatgpt.com'}
PATTERNS={
 'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'credential':r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|LTAI[A-Za-z0-9]{16,}|cpa_[A-Za-z0-9_-]{40,})\b',
 'personal-home':r'/(?:Users|home)/[A-Za-z0-9_.-]+/',
}
URL=re.compile(r'https?://[^\s"\x27<>`\\)]+')
IPV4=re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
issues=[];hosts={};files=0
for p in sorted(ROOT.rglob('*')):
 rel=p.relative_to(ROOT)
 if any(x in SKIP for x in rel.parts):continue
 if p.is_symlink():issues.append((str(rel),0,'symlink'));continue
 if not p.is_file():continue
 if rel.parts[0] in ('backups','secrets','auth-files') or rel.parts[:2] in (('monitor','data'),('monitor','secrets')):
  issues.append((str(rel),0,'private-runtime-directory'));continue
 if rel.parts[0]=='dist':continue
 if p.suffix in ('.sqlite','.db','.log') or p.name in ('loopback-auth.json','public-session.json','public-session-secret','cpa_management_key'):issues.append((str(rel),0,'private-runtime-file'));continue
 if p.name.startswith('._'):issues.append((str(rel),0,'os-metadata'));continue
 if p.name in ('.env','.npmrc','config.yaml') or p.name.endswith('-access.txt') or p.name.startswith(('cpa-key-policy-state','key-policy-state','credentials')):
  issues.append((str(rel),0,'private-runtime-file'));continue
 if rel.parts[:2]==('docs','images') and p.suffix=='.png':
  raw=p.read_bytes()
  valid=raw.startswith(bytes([137,80,78,71,13,10,26,10]));offset=8;ended=False
  while valid and offset+12<=len(raw):
   size=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8]
   if offset+12+size>len(raw) or kind not in (b'IHDR',b'IDAT',b'IEND',b'sRGB',b'gAMA',b'cHRM',b'pHYs',b'PLTE',b'tRNS'):valid=False;break
   offset+=12+size
   if kind==b'IEND':ended=True;break
  if not valid or not ended or offset!=len(raw):issues.append((str(rel),0,'image-metadata'))
  continue
 if p.name.endswith(('.so','.dll','.dylib','.zip','.tar.gz','.tsbuildinfo')):continue
 files+=1
 try:text=p.read_text()
 except UnicodeDecodeError:issues.append((str(rel),0,'unreviewed-binary'));continue
 for num,line in enumerate(text.splitlines(),1):
  for label,pattern in PATTERNS.items():
   if re.search(pattern,line):issues.append((str(rel),num,label))
  for raw in URL.findall(line):
   try:
    u=urllib.parse.urlsplit(raw);host=u.hostname
   except ValueError:issues.append((str(rel),num,'malformed-url'));continue
   if not host:continue
   hosts[host]=hosts.get(host,0)+1
   negative_fixture=rel.as_posix()=='web/src/store/session.test.ts' and host=='example.invalid' and u.username in (None,'user') and u.password in (None,'pass') and u.query in ('','key=test') and u.fragment in ('','secret')
   if (u.username or u.password) and not negative_fixture:issues.append((str(rel),num,'url-credentials'))
   if host not in HOSTS and not (host.endswith(('.example.com','.example.invalid','.example.test')) or host in ('example.com','example.invalid','example.test')):
    issues.append((str(rel),num,'unreviewed-url-host'))
   if re.search(r'(?i)(?:key|token|secret|signature)=',u.query) and not negative_fixture:issues.append((str(rel),num,'url-secret-parameter'))
  for raw in IPV4.findall(line):
   try:ip=ipaddress.ip_address(raw)
   except ValueError:continue
   if not (ip.is_loopback or ip.is_unspecified):issues.append((str(rel),num,'non-example-ip'))
# Never print credential values or unapproved URL contents.
print(json.dumps({'scanned_files':files,'issues':[{'file':f,'line':n,'category':c} for f,n,c in issues],'approved_hosts':sorted(h for h in hosts if h in HOSTS or h.endswith(('.example.com','.example.invalid','.example.test')))},indent=2))
sys.exit(1 if issues else 0)
