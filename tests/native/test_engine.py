import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
P=Path(__file__).resolve().parents[1]/'files/sidecamera_engine.py'
spec=importlib.util.spec_from_file_location('engine',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CC=NS(enabled=False,latActive=False,longActive=False)
def out(**changes):
 x=dict(canValid=True,standstill=True,gearShifter='park',vEgo=0.,vEgoRaw=0.,leftBlinker=False,rightBlinker=False);x.update(changes);return NS(**x)
class Tests(unittest.TestCase):
 def start(self,strategy='direct',view=7):
  e=m.Engine();e.update(0,CC,out(),0);e.observe(2,2,0x3ee,bytes((0,view,8,27,128,0,0,0)));e.observe(2,0,0x443,m.TRAILER_BASE);e.arm(2,strategy,20);return e
 def test_right_and_restore(self):
  e=self.start();self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[m.view_request(0x30)])
  e.observe(2.4,2,0x3ee,bytes.fromhex('0030081b80000000'));self.assertEqual(e.update(2.4,CC,out(rightBlinker=True),0),[]);self.assertEqual(e.phase,'holding')
  self.assertEqual(e.update(3,CC,out(),0),[m.view_request(7)])
 def test_left(self):
  e=self.start();self.assertEqual(e.update(2.1,CC,out(leftBlinker=True),0),[m.view_request(0x2f)])
 def test_gates(self):
  for changes in [dict(gearShifter='drive'),dict(vEgo=.1),dict(vEgoRaw=.1),dict(vEgo=float('nan')),dict(canValid=False),dict(standstill=False),dict(leftBlinker=True,rightBlinker=True)]:
   e=self.start();self.assertEqual(e.update(2.1,CC,out(**changes),0),[]);self.assertEqual(e.phase,'disabled')
  for name in ['enabled','latActive','longActive']:
   c=NS(**{k:k==name for k in ['enabled','latActive','longActive']});e=self.start();self.assertEqual(e.update(2.1,c,out(rightBlinker=True),0),[])
 def test_no_blind_retry(self):
  e=self.start();e.update(2.1,CC,out(rightBlinker=True),0)
  for t in [3,4,5]:self.assertEqual(e.update(t,CC,out(rightBlinker=True),0),[])
  self.assertEqual(e.phase,'failed')
 def test_wake(self):
  e=self.start('wake',0);self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[m.button(True)])
  e.observe(2.3,2,0x3ee,bytes.fromhex('0007081b80000000'));self.assertEqual(e.update(2.4,CC,out(rightBlinker=True),0),[])
  self.assertEqual(e.update(2.61,CC,out(rightBlinker=True),0),[m.button(False),m.view_request(0x30)])
  e.observe(2.8,2,0x3ee,bytes.fromhex('0030081b80000000'));e.update(2.8,CC,out(rightBlinker=True),0)
  self.assertEqual(e.update(3,CC,out(),0),[m.button(True)]);self.assertEqual(e.update(3.51,CC,out(),0),[m.button(False)])
 def test_user_override(self):
  e=self.start('wake',0);e.update(2.1,CC,out(rightBlinker=True),0);e.update(2.61,CC,out(rightBlinker=True),0)
  e.observe(3,2,0x3ee,bytes.fromhex('0026081b80000000'));self.assertEqual(e.update(3.1,CC,out(),0),[])
 def test_direct_requires_preopened(self):
  e=self.start(view=0);self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[])
 def test_trailer_is_explicit_bounded_and_restored(self):
  e=self.start('trailer');self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[(0x443,m.TRAILER_ON,2)])
  for t in [3.11,4.12]:
   e.observe(t,0,0x443,m.TRAILER_BASE);frames=e.update(t,CC,out(rightBlinker=True),0)
  self.assertIn(m.view_request(0x30),frames)
  e.observe(4.4,2,0x3ee,bytes.fromhex('0030081b80000000'));e.update(4.4,CC,out(rightBlinker=True),0)
  e.observe(5,0,0x443,m.TRAILER_BASE);self.assertEqual(e.update(5,CC,out(),0),[(0x443,m.TRAILER_BASE,2),m.view_request(7)])
 def test_no_virtual_when_actual_trailer(self):
  e=self.start('trailer');e.observe(2,0,0x443,bytes.fromhex('840010fffe000000'))
  self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[m.view_request(0x30)])
 def test_factory_connected_status_variant(self):
  e=self.start('trailer-factory');self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[(0x443,m.TRAILER_FACTORY,2)])
 def test_unknown_trailer_refused(self):
  e=self.start('trailer');e.observe(2,0,0x443,bytes.fromhex('040010fffe000000'));self.assertEqual(e.update(2.1,CC,out(rightBlinker=True),0),[])
 def test_status_changed_stops_virtual(self):
  e=self.start('trailer');e.update(2.1,CC,out(rightBlinker=True),0);e.observe(2.5,0,0x443,bytes.fromhex('840010fffe000000'));self.assertEqual(e.update(2.5,CC,out(rightBlinker=True),0),[]);self.assertFalse(e.virtual)
 def test_lease_expiry_and_stale_view(self):
  e=self.start();e.update(2.1,CC,out(rightBlinker=True),0);e.observe(3,2,0x3ee,bytes.fromhex('0030081b80000000'));e.until=3.1
  self.assertEqual(e.update(3.2,CC,out(rightBlinker=True),0),[m.view_request(7)]);self.assertEqual(e.phase,'disabled')
  e=self.start();self.assertEqual(e.update(5,CC,out(rightBlinker=True),0),[])
 def drive(self):return out(gearShifter='drive',brakePressed=True,gasPressed=False)
 def drive_start(self):
  e=m.Engine();e.arm(0,'direct',20,True);e.update(0,CC,self.drive(),0)
  e.observe(2.1,2,0x3ee,bytes.fromhex('0007081b80000000'));return e
 def test_drive_requires_explicit_flag_brake_and_zero_speed(self):
  d=self.drive();self.assertFalse(m.eligible(CC,d,0));self.assertTrue(m.eligible(CC,d,0,True))
  for changes in [dict(brakePressed=False),dict(gasPressed=True),dict(gearShifter='park'),dict(gearShifter='neutral'),dict(gearShifter='reverse'),dict(vEgo=.1),dict(vEgoRaw=.1),dict(vEgo=float('nan')),dict(standstill=False),dict(canValid=False),dict(leftBlinker=True,rightBlinker=True)]:
   d=self.drive();d.__dict__.update(changes);self.assertFalse(m.eligible(CC,d,0,True),changes)
 def test_drive_right_then_brake_release_cancels_without_resume(self):
  e=self.drive_start();d=self.drive();d.rightBlinker=True
  self.assertEqual(e.update(2.1,CC,d,0),[m.view_request(0x30)])
  d.brakePressed=False;self.assertEqual(e.update(2.2,CC,d,0),[]);self.assertEqual(e.phase,'disabled')
  d.brakePressed=True;e.observe(3,2,0x3ee,bytes.fromhex('0007081b80000000'))
  self.assertEqual(e.update(3,CC,d,0),[]);self.assertEqual(e.until,0)
 def test_drive_detects_native_side_without_injection(self):
  e=self.drive_start();d=self.drive();d.rightBlinker=True
  e.observe(2.1,2,0x3ee,bytes.fromhex('0030081b80000000'))
  self.assertEqual(e.update(2.1,CC,d,0),[]);self.assertEqual(e.phase,'holding');self.assertEqual(e.attempts,1)
 def test_drive_rejects_other_profiles(self):
  for profile in ('wake','trailer','trailer-factory'):
   with self.assertRaises(ValueError):m.Engine().arm(0,profile,20,True)
 def test_drive_loses_gear_motion_or_assistance_and_stops(self):
  for change in (dict(gearShifter='park'),dict(vEgo=.1),dict(gasPressed=True)):
   e=self.drive_start();d=self.drive();d.__dict__.update(change)
   self.assertEqual(e.update(2.1,CC,d,0),[]);self.assertEqual(e.until,0)
  e=self.drive_start();self.assertEqual(e.update(2.1,NS(enabled=True,latActive=False,longActive=False),self.drive(),0),[])
if __name__=='__main__':unittest.main()
