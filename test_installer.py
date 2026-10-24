"""Host-only transaction tests: no device, build, messaging or CAN access."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
spec=importlib.util.spec_from_file_location('installer',Path(__file__).with_name('setup.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Transactions(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);base=Path(self.temp.name)
  self.root=base/'device';self.pkg=base/'package';self.root.mkdir();self.pkg.mkdir()
  self.manifest={'a.py':{'stock':s.sha(b'old=1\n'),'installed':s.sha(b'new=2\n')},'helper.py':{'stock':None,'installed':s.sha(b'helper=3\n')}}
  (self.root/'a.py').write_bytes(b'old=1\n');(self.root/'a.py').chmod(0o755)
  for rel,data in [('a.py',b'new=2\n'),('helper.py',b'helper=3\n')]:
   p=self.pkg/'files'/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
  self.fw=self.root/'fw';self.fw.write_bytes(b'previous firmware');self.setting=base/'setting.json'
  self.artifact=base/'newfw';self.artifact.write_bytes(b'candidate firmware')
  record=dict(files=self.manifest,bluepilot=s.BLUEPILOT,panda=s.PANDA,baseline_firmware=s.digest(self.fw),firmware=str(self.artifact),sha256=s.digest(self.artifact))
  (self.pkg/'prepared.json').write_text(json.dumps(record))
  values=dict(ROOT=self.root,HERE=self.pkg,MANIFEST=self.manifest,FIRMWARE=self.fw,SETTING=self.setting,BACKUPS=base/'backups')
  self.patches=[patch.object(s,k,v) for k,v in values.items()]+[patch.object(s,'offroad'),patch.object(s,'revisions')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def transaction(self):
  with patch.object(s,'check_stock'),patch.object(s.subprocess,'run'):
   s.deploy()
 def test_install_then_restore_exact_files_modes_absence_and_settings(self):
  self.setting.write_text('{"enabled":true}')
  self.transaction();self.assertEqual(json.loads(self.setting.read_text()),{'enabled':False})
  self.assertTrue((self.root/'helper.py').exists());self.assertTrue((self.root/'prebuilt').exists())
  s.restore();self.assertEqual((self.root/'a.py').read_bytes(),b'old=1\n');self.assertEqual((self.root/'a.py').stat().st_mode & 0o777,0o755)
  self.assertFalse((self.root/'helper.py').exists());self.assertFalse((self.root/'prebuilt').exists())
  self.assertEqual(self.fw.read_bytes(),b'previous firmware');self.assertEqual(self.setting.read_text(),'{"enabled":true}')
 def test_import_failure_rolls_back(self):
  with patch.object(s,'check_stock'),patch.object(s.subprocess,'run',side_effect=RuntimeError('import failed')):
   with self.assertRaises(RuntimeError):s.deploy()
  self.assertEqual((self.root/'a.py').read_bytes(),b'old=1\n');self.assertFalse((self.root/'helper.py').exists());self.assertFalse(self.setting.exists())
  self.assertEqual(self.fw.read_bytes(),b'previous firmware')
 def test_corrupt_backup_rejected_before_restore_changes(self):
  self.transaction();r=json.loads((self.pkg/'installation.json').read_text())
  (Path(r['backup'])/r['entries']['a.py']['saved']).write_bytes(b'corrupt')
  with self.assertRaises(RuntimeError):s.restore()
  self.assertEqual((self.root/'a.py').read_bytes(),b'new=2\n');self.assertEqual(self.fw.read_bytes(),b'candidate firmware')
 def test_modified_prepared_artifact_rejected_without_changes(self):
  self.artifact.write_bytes(b'changed')
  with patch.object(s,'check_stock'):
   with self.assertRaises(RuntimeError):s.deploy()
  self.assertEqual((self.root/'a.py').read_bytes(),b'old=1\n');self.assertFalse((self.pkg/'installation.json').exists())
 def test_restore_rejects_newer_user_edits(self):
  self.transaction();(self.root/'a.py').write_bytes(b'user changes')
  with self.assertRaises(RuntimeError):s.restore()
  self.assertEqual((self.root/'a.py').read_bytes(),b'user changes')
 def test_idempotent_deploy_does_not_overwrite_backup(self):
  self.transaction();r=(self.pkg/'installation.json').read_bytes()
  with patch.object(s,'check_stock',side_effect=AssertionError('should not rebuild')):s.deploy()
  self.assertEqual((self.pkg/'installation.json').read_bytes(),r)
 def test_tampered_package_rejected(self):
  (self.pkg/'files/a.py').write_bytes(b'changed')
  with self.assertRaises(RuntimeError):s.package_check()
 def test_stock_preflight_refuses_unknown_source(self):
  (self.root/'a.py').write_bytes(b'user changes')
  with self.assertRaisesRegex(RuntimeError,'Expected exact stock source'):s.check_stock()
 def test_preexisting_symlink_is_not_overwritten(self):
  outside=Path(self.temp.name)/'outside';outside.write_bytes(b'keep')
  (self.root/'a.py').unlink();(self.root/'a.py').symlink_to(outside)
  with self.assertRaises(RuntimeError):s.atomic(self.root/'a.py',b'new')
  self.assertEqual(outside.read_bytes(),b'keep')
 def test_offroad_failure_stops_deployment(self):
  with patch.object(s,'check_stock'),patch.object(s,'offroad',side_effect=RuntimeError('started')):
   with self.assertRaises(RuntimeError):s.deploy()
  self.assertEqual((self.root/'a.py').read_bytes(),b'old=1\n');self.assertFalse((self.pkg/'installation.json').exists())
 def test_interrupted_install_mixed_files_can_restore(self):
  r=dict(s.snapshot(),state='backed-up',sha256=s.digest(self.artifact))
  (self.pkg/'installation.json').write_text(json.dumps(r));(self.root/'a.py').write_bytes(b'new=2\n')
  s.restore();self.assertEqual((self.root/'a.py').read_bytes(),b'old=1\n');self.assertFalse((self.root/'helper.py').exists())
if __name__=='__main__':unittest.main()
