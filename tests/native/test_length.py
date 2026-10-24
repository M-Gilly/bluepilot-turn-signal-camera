"""Compile the complete safety hooks in an isolated temporary fixture."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('complete_safety', P/'test_safety.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
OriginalTests = m.Tests
M = m.M
BASE = bytes.fromhex('00 00 FC 00 80 00 FC 40')
SHORT = bytes.fromhex('00 00 FC 00 80 00 12 40')

class LengthTests(unittest.TestCase):
  def setUp(self):
    M.reset(); M.seed(2); M.rx(0x227, BASE)

  def test_exact_field_cleanup_and_forwarding(self):
    self.assertTrue(M.tx(0x227, SHORT, 2))
    self.assertEqual(M.l.lab_fwd(0, 0x227), -1)
    self.assertEqual(M.l.lab_fwd(2, 0x227), 0)
    self.assertFalse(M.tx(0x227, SHORT, 2))
    self.assertTrue(M.tx(0x227, BASE, 2))
    self.assertEqual(M.l.lab_fwd(0, 0x227), 2)
    self.assertFalse(M.tx(0x227, BASE, 2))

  def test_all_payload_mutations(self):
    for byte in range(8):
      for value in range(256):
        d = bytearray(SHORT); d[byte] = value
        if bytes(d) in (SHORT, BASE): continue
        self.setUp()
        self.assertFalse(M.tx(0x227, bytes(d), 2), (byte, value))

  def test_wrong_bus_stale_stationary_and_signal(self):
    self.assertFalse(M.tx(0x227, SHORT, 0))
    self.setUp(); M.time(1200000)
    self.assertFalse(M.tx(0x227, SHORT, 2))
    for signal in [0, 3]:
      self.setUp(); M.seed(signal)
      self.assertFalse(M.tx(0x227, SHORT, 2))

  def test_lease_expiry_controls_motion_and_real_profile(self):
    for flags in [(1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)]:
      self.setUp(); M.l.lab_flags(*flags)
      self.assertFalse(M.tx(0x227, SHORT, 2))
    self.setUp(); self.assertTrue(M.tx(0x227, SHORT, 2))
    M.time(2200000); M.seed(2); M.rx(0x227, BASE)
    self.assertEqual(M.l.lab_fwd(0, 0x227), 2)

  def test_restart_after_sender_stops_without_cleanup(self):
    self.assertTrue(M.tx(0x227, SHORT, 2))
    M.time(3100000); M.seed(0); M.rx(0x227, BASE)
    self.assertEqual(M.l.lab_fwd(0, 0x227), 2)
    M.seed(1); self.assertTrue(M.tx(0x227, SHORT, 2))

  def test_missing_cleanup_rearms_both_messages(self):
    trailer=bytes.fromhex('80 00 10 FF FC 00 00 00')
    self.assertTrue(M.tx(0x227,SHORT,2));self.assertTrue(M.tx(0x443,trailer,2))
    M.time(4000000);M.seed(0)
    M.time(14000000);M.seed(0);M.seed(1)
    self.assertTrue(M.tx(0x227,SHORT,2));self.assertTrue(M.tx(0x443,trailer,2))

  def test_control_transition_then_neutral_recovery(self):
    trailer=bytes.fromhex('80 00 10 FF FC 00 00 00')
    self.assertTrue(M.tx(0x227,SHORT,2));self.assertTrue(M.tx(0x443,trailer,2))
    M.l.lab_flags(0,1,0,0)
    self.assertEqual(M.l.lab_fwd(0,0x443),2)
    M.time(4000000);M.seed(0);M.l.lab_flags(0,0,0,0)
    M.time(14000000);M.seed(0);M.seed(2)
    self.assertTrue(M.tx(0x443,trailer,2))

  def test_budget_neutral_reset_and_unrelated_forwarding(self):
    for i in range(10):
      M.time(1000000+i*1000000); M.seed(2); M.rx(0x227, BASE)
      self.assertTrue(M.tx(0x227, SHORT, 2))
    M.time(11000000); M.seed(2); M.rx(0x227, BASE)
    self.assertFalse(M.tx(0x227, SHORT, 2))
    self.assertTrue(M.tx(0x227, BASE, 2))
    M.time(13000000); M.seed(0); M.rx(0x227, BASE)
    M.seed(1); self.assertTrue(M.tx(0x227, SHORT, 2))
    m.A.reset(); m.A.seed()
    for bus in [0,1,2]:
      for address in range(2048):
        if bus == 0 and address == 0x227: continue
        self.assertEqual(M.l.lab_fwd(bus,address), m.A.l.lab_fwd(bus,address))

if __name__ == '__main__':
  unittest.main()
