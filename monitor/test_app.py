import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('app',Path(__file__).with_name('app.py'));a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Tests(unittest.TestCase):
 def test_mutations_rejected_without_reading_credentials(self):
  for method in ['PATCH','PUT','DELETE','POST']:
   with self.assertRaises(ValueError):a.api('plugins/cpa-key-policy/keys',{'id':'demo-key'},method)
 def test_http_write_methods_are_readonly(self):
  from unittest.mock import Mock
  h=object.__new__(a.Handler);h.send=Mock()
  for method in ['do_POST','do_PATCH','do_PUT','do_DELETE']:
   getattr(h,method)();self.assertEqual(h.send.call_args.args[0],405)
 def test_no_settings_in_frontend(self):
  root=Path(__file__).parent
  page=(root/'index.html').read_text();js=(root/'app.js').read_text()
  self.assertNotIn('<form',page);self.assertNotIn('<input',page);self.assertNotIn('/api/budget',js)
 def test_select_weekly_primary(self):
  got=a.normalize_quota({'rate_limit':{'primary_window':{'limit_window_seconds':604800,'used_percent':39,'reset_at':2000}}},1000)
  self.assertEqual(got['remaining_percent'],61)
 def test_reject_expired_and_invalid(self):
  for val,end in [(30,999),(101,2000),(float('nan'),2000)]:
   with self.assertRaises(ValueError):a.normalize_quota({'rate_limit':{'primary_window':{'limit_window_seconds':604800,'used_percent':val,'reset_at':end}}},1000)
 def test_confirm_cycle_twice(self):
  old={'reset_at':2000,'used_percent':90,'at':1000};new={'reset_at':5000,'used_percent':1,'at':1100}
  kept,pending,error=a.accept_quota(old,new,None);self.assertEqual(kept,old);self.assertTrue(error)
  new2={**new,'at':1140};kept,pending,error=a.accept_quota(old,new2,pending);self.assertEqual(kept,new2);self.assertFalse(error)
 def test_rollback_preserves(self):
  old={'reset_at':3000,'used_percent':50,'at':1000};new={'reset_at':2000,'used_percent':10,'at':1100}
  self.assertEqual(a.accept_quota(old,new,None)[0],old)
 def test_same_cycle_usage_decrease_preserves(self):
  old={'reset_at':3000,'used_percent':50,'at':1000};new={**old,'used_percent':20,'at':1100}
  self.assertEqual(a.accept_quota(old,new,None)[0],old)
 def test_no_secret_in_clean_key(self):
  k={'id':'demo-key','key':'SECRET','key_preview':'SECRET','models':[]};self.assertNotIn('SECRET',str(a.clean_key(k)))
 def test_usage_private_fields_are_not_forwarded(self):
  k={'id':'demo','models':[],'usage':{'weekly_usd':4,'key_hash':'PRIVATE','account_ref':'PRIVATE','history':['PRIVATE']}}
  clean=a.clean_key(k);self.assertEqual(clean['usage']['weekly_usd'],4);self.assertNotIn('PRIVATE',str(clean))
 def test_snapshot_omits_account_and_cycle_history(self):
  from unittest.mock import patch
  official={'account_ref':'PRIVATE','reset_at':9999999999,'at':9999999999,'remaining_percent':50}
  cached={'official':official,'cycle':{'history':['PRIVATE']},'plugin':{'keys':[],'at':None}}
  with patch.object(a,'load',lambda name:cached.get(name)):
   self.assertNotIn('PRIVATE',str(a.snapshot()))
 def test_disabled_cycle_does_not_write_to_plugin(self):
  from unittest.mock import patch,Mock
  now=2000000000
  official={'status_code':200,'body':{'rate_limit':{'primary_window':{'limit_window_seconds':604800,'used_percent':20,'reset_at':now+3600}}}}
  fake=Mock(side_effect=[{'files':[{'provider':'codex','auth_index':'demo'}]},official])
  with patch.object(a,'api',fake),patch.object(a,'load',lambda name:None),patch.object(a,'save'),patch.object(a,'CYCLE_SYNC_ENABLED',False),patch.object(a.time,'time',lambda:now):
   a.sync_official()
  self.assertEqual([x.args[0] for x in fake.call_args_list],['auth-files','api-call'])
if __name__=='__main__':unittest.main()
