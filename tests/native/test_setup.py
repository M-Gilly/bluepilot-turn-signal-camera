import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
B=Path(__file__).resolve().parents[1]
def load():
 spec=importlib.util.spec_from_file_location('installer',B/'setup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.i=load();self.i.ROOT=self.base/'openpilot';self.i.BUNDLE=self.base/'bundle';self.i.BACKUPS=self.base/'backup';self.i.BUNDLE.mkdir();shutil.copytree(B/'files',self.i.BUNDLE/'files')
  for name in ['manifest.json','camera.py','diagnose_ford_tests.py','reviewed-stock-ford-results.json']:shutil.copyfile(B/name,self.i.BUNDLE/name)
  self.manifest=json.loads((B/'manifest.json').read_text());self.root=self.i.ROOT
  for relative,info in self.manifest['files'].items():
   p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True)
   if info['stock'] is not None:p.write_bytes((B/'files'/(info['source']+'.stock')).read_bytes())
  self.fw=self.root/'panda/board/obj/panda_h7.bin.signed';self.fw.parent.mkdir(parents=True,exist_ok=True);self.fw.write_bytes(b'initial-firmware')
  self.i.revision=lambda p:self.manifest['panda_commit' if p.name=='panda' else 'bluepilot_commit']
  self.i.require_offroad=lambda:None;self.i.firmware_path=lambda:self.fw
  self.i.verify_sdk=lambda environment:None
  self.orig_check=self.i.subprocess.check_output;self.i.subprocess.check_output=lambda *a,**k:''
  self.orig_which=self.i.shutil.which;self.i.shutil.which=lambda tool,**kwargs:'/existing/'+tool
  self.fail=None;self.change=None;self.commands=[]
  def logged(command,label,logs,env):
   self.commands.append((label,command))
   if label in ('01-stock-ford-tests','03-modified-ford-tests','02-installed-ford-tests'):
    report=json.loads((self.i.BUNDLE/'reviewed-stock-ford-results.json').read_text())['stock']
    if self.change==label:report['rows'][0]['trace_sha256']='changed'
    Path(command[command.index('--output')+1]).write_text(json.dumps(report))
   if 'stock-firmware' in label:self.fw.write_bytes(b'built-from-clean-stock-source')
   if 'modified-firmware' in label:self.fw.write_bytes(b'built-modified-firmware')
   if self.fail==label:raise RuntimeError('simulated '+label+' failure')
  self.i.run_logged=logged
 def tearDown(self):
  self.i.subprocess.check_output=self.orig_check;self.i.shutil.which=self.orig_which;self.temp.cleanup()
 def main(self,action,*options):
  sys.argv=['setup.py',action]+list(options)
  with contextlib.redirect_stdout(io.StringIO()):return self.i.main()
 def assert_stock(self):
  for relative,info in self.manifest['files'].items():
   p=self.root/relative
   if info['stock'] is None:self.assertFalse(p.exists())
   else:self.assertEqual(self.i.digest(p.read_bytes()),info['stock'])
 def test_install_and_restore_source_and_firmware(self):
  self.assertEqual(self.main('install'),0);self.assertNotEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
  self.assertEqual(self.main('restore'),0);self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
 def test_failing_modified_tests_restore(self):
  self.fail='03-modified-ford-tests'
  with self.assertRaises(RuntimeError):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
 def test_changed_fresh_stock_results_stop_before_build(self):
  self.change='01-stock-ford-tests'
  with self.assertRaisesRegex(RuntimeError,'comparison changed'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
  self.assertFalse((self.i.BUNDLE/'installation.json').exists())
 def test_changed_installed_results_restore(self):
  self.change='03-modified-ford-tests'
  with self.assertRaisesRegex(RuntimeError,'comparison changed'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
 def test_reviewed_baseline_tampering_refused(self):
  (self.i.BUNDLE/'reviewed-stock-ford-results.json').write_text('{}')
  with self.assertRaisesRegex(RuntimeError,'Validation checksum'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_diagnostic_tampering_refused(self):
  (self.i.BUNDLE/'diagnose_ford_tests.py').write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'Validation checksum'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_modified_suite_uses_actual_installed_headers(self):
  self.main('install')
  command=next(c for label,c in self.commands if label=='03-modified-ford-tests')
  self.assertEqual(command[command.index('--worker')+1],'installed')
 def test_truck_started_during_stock_tests_stops_before_build(self):
  calls=[]
  def offroad():
   calls.append(1)
   if len(calls)==2:raise RuntimeError('truck started')
  self.i.require_offroad=offroad
  with self.assertRaisesRegex(RuntimeError,'truck started'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_truck_started_after_source_install_restores(self):
  calls=[]
  def offroad():
   calls.append(1)
   if len(calls)==4:raise RuntimeError('truck started')
  self.i.require_offroad=offroad
  with self.assertRaisesRegex(RuntimeError,'truck started'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
 def test_failing_modified_build_restores_firmware(self):
  self.fail='05-modified-firmware-build'
  with self.assertRaises(RuntimeError):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
 def test_failing_stock_build_preserves_initial_artifact(self):
  self.fail='02-stock-firmware-build'
  with self.assertRaises(RuntimeError):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_changed_source_refused(self):
  p=self.root/'opendbc_repo/opendbc/car/ford/carcontroller.py';p.write_text('different')
  with self.assertRaises(RuntimeError):self.main('install')
  self.assertEqual(p.read_text(),'different');self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_changed_file_not_overwritten_by_restore(self):
  self.main('install');p=self.root/'opendbc_repo/opendbc/car/ford/carcontroller.py';p.write_text('later-user-edit')
  with self.assertRaises(RuntimeError):self.main('restore')
  self.assertEqual(p.read_text(),'later-user-edit')
 def test_wrong_revision_refused(self):
  self.i.revision=lambda p:'different'
  with self.assertRaises(RuntimeError):self.main('install')
  self.assert_stock()
 def test_only_exact_spinner_path_is_excluded(self):
  self.i.subprocess.check_output=self.orig_check
  repo=self.base/'git-test';repo.mkdir()
  def git(*args):
   return self.i.subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
  git('init')
  spinner=repo/'sunnypilot/selfdrive/assets/images/spinner_sunnypilot.png'
  spinner.parent.mkdir(parents=True);spinner.write_bytes(b'original')
  source=repo/'controller.py';source.write_text('original')
  other_image=spinner.with_name('other.png');other_image.write_bytes(b'original')
  git('add','.')
  git('-c','user.name=Installer Test','-c','user.email=test@example.invalid','commit','-m','baseline')
  spinner.write_bytes(b'user-image')
  self.assertEqual(self.i.tracked_changes(repo,allow_spinner=True),'')
  self.assertIn('spinner_sunnypilot.png',self.i.tracked_changes(repo))
  git('add','.')
  self.assertEqual(self.i.tracked_changes(repo,allow_spinner=True),'')
  source.write_text('user-source');other_image.write_bytes(b'user-other-image')
  dirty=self.i.tracked_changes(repo,allow_spinner=True)
  self.assertIn('controller.py',dirty);self.assertIn('other.png',dirty)
  self.assertNotIn('spinner_sunnypilot.png',dirty)
  self.assertEqual(spinner.read_bytes(),b'user-image')
 def test_other_tracked_changes_still_block_install(self):
  self.i.subprocess.check_output=lambda *a,**k:' M controller.py\n'
  with self.assertRaisesRegex(RuntimeError,'Tracked changes exist'):self.main('install')
  self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'initial-firmware')
 def test_emergency_restore_without_running_bluepilot(self):
  self.main('install');p=self.root/'opendbc_repo/opendbc/car/ford/carcontroller.py';p.write_text('later-user-edit')
  def unavailable():raise RuntimeError('no deviceState')
  self.i.require_offroad=unavailable
  self.assertEqual(self.main('restore','--emergency-offroad'),0);self.assert_stock();self.assertEqual(self.fw.read_bytes(),b'built-from-clean-stock-source')
  saved=list(self.i.BACKUPS.glob('*/emergency-pre-restore/opendbc_repo/opendbc/car/ford/carcontroller.py'))
  self.assertEqual(saved[0].read_text(),'later-user-edit')
 def previous_install(self):
  self.main('install');self.commands=[]
  for relative,info in self.manifest['files'].items():
   if 'previous_modified' in info:(self.root/relative).write_bytes((B/'files'/(info['source']+'.previous')).read_bytes())
 def test_python_update_preserves_firmware_and_stock_restore(self):
  self.previous_install();firmware=self.fw.read_bytes();self.assertEqual(self.main('update-python'),0)
  self.assertEqual(self.fw.read_bytes(),firmware)
  for relative,info in self.manifest['files'].items():self.assertEqual(self.i.digest((self.root/relative).read_bytes()),info['modified'])
  self.assertFalse(any('firmware' in label for label,command in self.commands))
  self.assertEqual(self.main('restore'),0);self.assert_stock()
 def test_failed_python_update_restores_previous_helpers(self):
  self.previous_install();self.fail='02-installed-ford-tests';firmware=self.fw.read_bytes()
  with self.assertRaises(RuntimeError):self.main('update-python')
  for relative,info in self.manifest['files'].items():
   if 'previous_modified' in info:self.assertEqual(self.i.digest((self.root/relative).read_bytes()),info['previous_modified'])
  self.assertEqual(self.fw.read_bytes(),firmware);self.assertEqual(self.main('restore'),0);self.assert_stock()
 def test_changed_update_target_refused(self):
  self.previous_install();p=self.root/'opendbc_repo/opendbc/car/ford/sidecamera_engine.py';p.write_text('user changes')
  with self.assertRaisesRegex(RuntimeError,'Installed file changed'):self.main('update-python')
  self.assertEqual(p.read_text(),'user changes')
 def test_changed_firmware_refuses_python_update(self):
  self.previous_install();self.fw.write_bytes(b'other-firmware')
  with self.assertRaisesRegex(RuntimeError,'firmware artifact changed'):self.main('update-python')
  self.assertEqual(self.fw.read_bytes(),b'other-firmware')
 def test_changed_native_decision_restores_previous_helpers(self):
  self.previous_install();self.change='02-installed-ford-tests'
  with self.assertRaisesRegex(RuntimeError,'comparison changed'):self.main('update-python')
  for relative,info in self.manifest['files'].items():
   if 'previous_modified' in info:self.assertEqual(self.i.digest((self.root/relative).read_bytes()),info['previous_modified'])
 def test_brake_mode_update_offroad_loss_restores_previous_helpers(self):
  self.previous_install();calls=[]
  def offroad():
   calls.append(1)
   if len(calls)==3:raise RuntimeError('truck started')
  self.i.require_offroad=offroad
  with self.assertRaisesRegex(RuntimeError,'truck started'):self.main('update-python')
  for relative,info in self.manifest['files'].items():
   if 'previous_modified' in info:self.assertEqual(self.i.digest((self.root/relative).read_bytes()),info['previous_modified'])
if __name__=='__main__':unittest.main()
