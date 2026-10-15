"""Publication regressions: runtime ledgers must never pass source review."""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
SCANNER=Path(__file__).with_name('check-public-source.py')
class PublicationTests(unittest.TestCase):
 def scan(self,files):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);(root/'scripts').mkdir();script=root/'scripts/check-public-source.py';shutil.copyfile(SCANNER,script)
   for name in files:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
   result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
   return result.returncode,json.loads(result.stdout)
 def test_runtime_ledgers_and_credential_directories_rejected(self):
  for name in ['internal/plugin/cpa-key-policy-state.json','key-policy-state.backup.json','monitor/data/cache.json','monitor/secrets/management-secret']:
   with self.subTest(name=name):
    code,result=self.scan([name]);self.assertEqual(code,1);self.assertTrue(any(issue['file']==name for issue in result['issues']))
 def test_public_example_is_allowed(self):
  code,result=self.scan(['monitor/examples/demo-state.json']);self.assertEqual(code,0);self.assertEqual(result['issues'],[])
if __name__=='__main__':unittest.main()
