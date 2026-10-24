from collections import deque
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
B=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
E=load('engine',B/'files/sidecamera_engine.py')
for name in ['opendbc','opendbc.car','opendbc.car.ford']:
 module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module
sys.modules['opendbc.car.ford.sidecamera_engine']=E
R=load('runtime',B/'files/sidecamera_runtime.py')
NS=types.SimpleNamespace
CC=NS(enabled=False,latActive=False,longActive=False)
def out(**kw):
 x=dict(canValid=True,standstill=True,gearShifter='park',vEgo=0.,vEgoRaw=0.,leftBlinker=False,rightBlinker=False);x.update(kw);return NS(**x)
class Clock:
 def __init__(self):self.now=10.
 def monotonic(self):return self.now
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name);self.clock=Clock();R.time=self.clock;self.queue=deque()
  messaging=types.ModuleType('cereal.messaging');messaging.sub_sock=lambda *a,**k:'can';messaging.recv_one_or_none=lambda socket:self.queue.popleft() if self.queue else None
  cereal=types.ModuleType('cereal');cereal.messaging=messaging;sys.modules['cereal']=cereal;sys.modules['cereal.messaging']=messaging
  self.h=R.SideCameraRuntime(self.directory);self.h.update(CC,out(),0)
 def tearDown(self):self.temp.cleanup()
 def observe(self,view=7,src=2,age=0):
  self.queue.append(NS(logMonoTime=int((self.clock.now-age)*1e9),can=[NS(src=src,address=0x3ee,dat=bytes([0,view,8,27,128,0,0,0]))]))
 def request(self,**kw):
  d=dict(session=self.h.session,request_id='a'*32,created=self.clock.now,expires=self.clock.now+5,command='arm',strategy='direct',seconds=20);d.update(kw)
  (self.directory/'request.json').write_text(json.dumps(d))
 def ready(self):self.clock.now=12.1;self.observe();self.request();self.h.update(CC,out(),0)
 def test_automatic_request_and_restore(self):
  self.ready();self.assertTrue(self.h.armed_once);self.clock.now=12.3;self.assertEqual(self.h.update(CC,out(rightBlinker=True),0),[E.view_request(0x30)])
  self.clock.now=12.5;self.observe(0x30);self.assertEqual(self.h.update(CC,out(rightBlinker=True),0),[])
  self.clock.now=12.7;self.assertEqual(self.h.update(CC,out(),0),[E.view_request(7)])
 def test_invalid_and_stale_session(self):
  for kw in [dict(session='old'),dict(expires=9),dict(command='raw'),dict(strategy='anything')]:
   self.clock.now+=.2;self.request(**kw);self.assertEqual(self.h.update(CC,out(),0),[]);self.assertFalse(self.h.armed_once);self.assertFalse((self.directory/'request.json').exists())
 def test_cancel_beats_pending_arm(self):
  self.clock.now=12.1;self.request();c=dict(session=self.h.session,request_id='b'*32,created=12.1,expires=17.1,command='disarm');(self.directory/'cancel.json').write_text(json.dumps(c))
  self.assertEqual(self.h.update(CC,out(),0),[]);self.assertEqual(self.h.engine.phase,'disabled');self.assertFalse((self.directory/'request.json').exists())
 def test_rearm_and_turn_active_refused(self):
  self.ready();self.clock.now+=.2;self.request();self.assertEqual(self.h.update(CC,out(),0),[]);self.assertEqual(self.h.request_result,'refused')
 def test_tx_echo_cannot_fake_feedback(self):
  self.ready();self.clock.now=12.3;self.h.update(CC,out(rightBlinker=True),0);self.clock.now=12.5;self.observe(0x30,128);self.h.update(CC,out(rightBlinker=True),0);self.assertEqual(self.h.engine.view,7)
 def test_stale_batch_not_freshened(self):
  self.clock.now=15;self.observe(7,age=2);self.h.update(CC,out(),0);self.assertIsNone(self.h.engine.view)
 def test_exception_does_not_crash_controller(self):
  def broken(socket):raise RuntimeError('mock failure')
  self.h.messaging.recv_one_or_none=broken;self.assertEqual(self.h.update(CC,out(),0),[]);self.assertFalse(self.h.available)
 def test_drive_arm_and_brake_release(self):
  d=out(gearShifter='drive',brakePressed=True,gasPressed=False)
  self.clock.now=12.1;self.observe();self.request(stationary_drive=True)
  self.h.update(CC,d,0);self.assertEqual(self.h.request_result,'armed')
  self.clock.now=14.2;self.observe();d.rightBlinker=True
  self.assertEqual(self.h.update(CC,d,0),[E.view_request(0x30)])
  self.clock.now=14.3;d.brakePressed=False
  self.assertEqual(self.h.update(CC,d,0),[]);self.assertEqual(self.h.engine.phase,'disabled')
  self.assertEqual(self.h.engine.until,0)
 def test_drive_not_armed_by_old_or_invalid_command(self):
  for fields in ({},{'stationary_drive':'yes'},{'stationary_drive':True,'strategy':'trailer'}):
   self.clock.now+=.2;self.request(**fields)
   self.assertEqual(self.h.update(CC,out(gearShifter='drive',brakePressed=True,gasPressed=False),0),[])
   self.assertFalse(self.h.armed_once);self.assertEqual(self.h.request_result,'refused')
if __name__=='__main__':unittest.main()
