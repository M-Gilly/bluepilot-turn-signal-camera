"""Compile complete pinned safety code, then exercise its real RX/TX/FWD hooks."""
import ctypes as C
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
B=Path(__file__).resolve().parent
CC=shutil.which('clang') or shutil.which('cc') or shutil.which('gcc')
if not CC:raise RuntimeError('A host C compiler is required; no compiler is installed by this test.')
TEMP=tempfile.TemporaryDirectory(prefix='sidecamera-tests-')
class Lib:
 def __init__(self,name):
  output=Path(TEMP.name)/(name+'.so')
  subprocess.run([CC,'-shared','-fPIC','-O1','-Wall','-Wextra','-Werror','-DALLOW_DEBUG','-I'+str(B/name),str(B/'lab.c'),'-o',str(output),'-lm'],check=True)
  self.l=C.CDLL(str(output))
  for n in ['lab_rx','lab_tx']:getattr(self.l,n).argtypes=[C.c_int,C.c_int,C.c_int,C.c_char_p]
 def reset(self,param=2,sp=0):self.t=1000000;self.counter=0;self.l.lab_time(self.t);assert self.l.lab_init(param,sp)==0
 def rx(self,a,data,b=0):return bool(self.l.lab_rx(a,b,len(data),data))
 def tx(self,a,data,b=0):return bool(self.l.lab_tx(a,b,len(data),data))
 def time(self,t):self.t=t;self.l.lab_time(C.c_uint32(t))
 def seed(self,signal=0):
  assert self.rx(0x213,bytes([0,0,0,8,0,0,0,0]))
  self.counter=(self.counter+1)%16
  assert self.rx(0x415,bytes([0,0,0xc0 | (self.counter<<2),0xfc-self.counter,0,0,0,0]))
  assert self.rx(0x83,bytes([signal<<4,0,0,0,0,0,0,0]))
A=Lib('baseline');M=Lib('modified')
def view(v=0x30):return bytes([0,v,8,0x1b,0x81,0x50,0,0])
BASE=bytes.fromhex('000010fffe000000');ON=bytes.fromhex('800010fffe000000')
class Tests(unittest.TestCase):
 def setUp(self):M.reset();M.seed()
 def test_requests_and_global_allowlist(self):
  A.reset();A.seed();self.assertFalse(A.tx(0x3e2,view()))
  for v in [0x2f,0x30,7,0x2c,0xb,0x26]:M.reset();M.seed();self.assertTrue(M.tx(0x3e2,view(v)))
  self.assertFalse(M.tx(0x3e2,view(),2));self.assertFalse(M.tx(0x3ee,bytes.fromhex('0030081b80000000')))
 def test_all_payload_substitutions(self):
  for byte in range(8):
   for value in range(256):
    p=bytearray(view());p[byte]=value
    if byte==1 and value in [0x2f,0x30,7,0x2c,0xb,0x26]:continue
    if bytes(p)==view():continue
    M.reset();M.seed();self.assertFalse(M.tx(0x3e2,bytes(p)),(byte,value))
 def test_stale_missing_motion_and_controls(self):
  M.reset();self.assertFalse(M.tx(0x3e2,view()))
  for flags in [(1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)]:
   M.reset();M.seed();M.l.lab_flags(*flags);self.assertFalse(M.tx(0x3e2,view()))
  M.reset();M.seed();M.time(1200000);self.assertFalse(M.tx(0x3e2,view()))
  M.reset();M.seed(3);self.assertFalse(M.tx(0x3e2,view()))
  M.reset();M.seed();M.rx(0x213,bytes(8));self.assertFalse(M.tx(0x3e2,view()))
  M.reset();M.seed();M.rx(0x415,bytes([0,1,0xc0,0xfb,0,0,0,0]));self.assertFalse(M.tx(0x3e2,view()))
 def test_bad_rx_integrity_cannot_prime(self):
  M.reset();M.rx(0x213,bytes([0,0,0,8,0,0,0,0]));M.rx(0x83,bytes(8))
  self.assertFalse(M.rx(0x415,bytes(8)));self.assertFalse(M.tx(0x3e2,view()))
 def test_rate_and_budget(self):
  self.assertTrue(M.tx(0x3e2,view()));self.assertFalse(M.tx(0x3e2,view()))
  for i in range(1,8):M.time(1000000+i*250000);M.seed();self.assertTrue(M.tx(0x3e2,view()))
  M.time(3000000);M.seed();self.assertFalse(M.tx(0x3e2,view()))
 def test_button_exact_pulse_and_two_press_budget(self):
  on=bytes.fromhex('0001000000000000');off=bytes(8)
  self.assertFalse(M.tx(0x192,off));self.assertTrue(M.tx(0x192,on));self.assertFalse(M.tx(0x192,on))
  M.time(1500000);M.seed();self.assertTrue(M.tx(0x192,off));self.assertFalse(M.tx(0x192,on))
  M.time(3000000);M.seed();self.assertTrue(M.tx(0x192,on));M.time(3500000);M.seed();self.assertTrue(M.tx(0x192,off))
  M.time(5000000);M.seed();self.assertFalse(M.tx(0x192,on))
 def test_trailer_payload_network_rate_and_deadman(self):
  self.assertFalse(M.tx(0x443,ON,0));self.assertFalse(M.tx(0x443,bytes.fromhex('c40010fffe000000'),2))
  self.assertEqual(M.l.lab_fwd(0,0x443),2);self.assertTrue(M.tx(0x443,ON,2));self.assertFalse(M.tx(0x443,ON,2))
  self.assertEqual(M.l.lab_fwd(0,0x443),-1);self.assertEqual(M.l.lab_fwd(2,0x443),0)
  for t,expected in [(2100000,-1),(2200000,2)]:M.time(t);M.seed();self.assertEqual(M.l.lab_fwd(0,0x443),expected)
 def test_factory_connected_status_variant(self):
  self.assertTrue(M.tx(0x443,bytes.fromhex('840010fffe000000'),2))
 def test_trailer_only_suppresses_one_forwarding_path(self):
  self.assertTrue(M.tx(0x443,ON,2));A.reset();A.seed()
  for bus in [0,1,2]:
   for address in range(2048):
    if bus==0 and address==0x443:continue
    self.assertEqual(M.l.lab_fwd(bus,address),A.l.lab_fwd(bus,address),(bus,address))
  self.assertTrue(M.tx(0x443,BASE,2));self.assertEqual(M.l.lab_fwd(0,0x443),2)
 def test_trailer_hard_window_and_count(self):
  for i in range(10):
   M.time(1000000+i*1000000);M.seed();self.assertTrue(M.tx(0x443,ON,2))
  M.time(11000000);M.seed();self.assertFalse(M.tx(0x443,ON,2));self.assertEqual(M.l.lab_fwd(0,0x443),2)
 def test_stationary_failure_restores_forwarding(self):
  self.assertTrue(M.tx(0x443,ON,2));M.l.lab_flags(0,0,1,0);self.assertEqual(M.l.lab_fwd(0,0x443),2)
 def test_non_camera_tx_matches_stock(self):
  rng=random.Random(20261022)
  addresses=[0x83,0x186,0x18a,0x3ca,0x3d3,0x3d6,0x3d8,0x3ee,0x415,0x123]
  for param in [0,1,2,3]:
   for sp in [0,15]:
    A.reset(param,sp);M.reset(param,sp)
    for i in range(2000):
     flags=[rng.randrange(2) for _ in range(4)];A.l.lab_flags(*flags);M.l.lab_flags(*flags)
     addr=rng.choice(addresses);bus=rng.randrange(3);data=rng.randbytes(8)
     self.assertEqual(M.tx(addr,data,bus),A.tx(addr,data,bus),(param,sp,addr,bus,data.hex()))
 def test_idle_forwarding_matches_stock(self):
  A.reset();M.reset()
  for bus in [0,1,2]:
   for address in range(2048):self.assertEqual(M.l.lab_fwd(bus,address),A.l.lab_fwd(bus,address))
if __name__=='__main__':unittest.main()
