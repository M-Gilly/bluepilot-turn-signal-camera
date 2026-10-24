import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT/'files/opendbc_repo/opendbc/car/ford/sidecamera_engine.py'
spec = importlib.util.spec_from_file_location('opendbc.car.ford.sidecamera_engine', ENGINE)
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
sys.modules[spec.name] = engine
spec = importlib.util.spec_from_file_location('opendbc.car.ford.sidecamera_settings', ROOT/'files/opendbc_repo/opendbc/car/ford/sidecamera_settings.py')
settings = importlib.util.module_from_spec(spec); spec.loader.exec_module(settings)
sys.modules[spec.name] = settings
spec = importlib.util.spec_from_file_location('toggle_runtime', ROOT/'files/opendbc_repo/opendbc/car/ford/sidecamera_runtime.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
CC = NS(enabled=False, latActive=False, longActive=False)

def out(**kw):
  d=dict(canValid=True,standstill=True,gearShifter='drive',brakePressed=True,gasPressed=False,
         vEgo=0.,vEgoRaw=0.,leftBlinker=False,rightBlinker=False)
  d.update(kw); return NS(**d)

class Tests(unittest.TestCase):
  def setUp(self): self.e=r.LengthAttempt()

  def tick(self,t,enabled=True,**kw):
    self.e.observe(t,0,0x227,r.LENGTH_BASE)
    self.e.observe(t,0,0x443,r.TRAILER_BASES[1])
    return self.e.update(t,CC,out(**kw),0,enabled=enabled)

  def start(self):
    self.tick(0);self.tick(2.1);self.tick(2.2,rightBlinker=True)
    self.tick(2.56,rightBlinker=True)

  def test_off_prevents_activation(self):
    self.tick(0,False);self.tick(2.1,False)
    self.assertEqual(self.tick(2.2,False,rightBlinker=True),[])
    self.assertFalse(self.e.active)

  def test_switch_off_cleans_up_once(self):
    self.start()
    self.assertEqual(self.tick(2.7,False,rightBlinker=True),
                     [(0x443,r.TRAILER_BASES[1],2),(0x227,r.LENGTH_BASE,2)])
    self.assertEqual(self.tick(2.8,False,rightBlinker=True),[])

  def test_off_never_sends_after_brake_release(self):
    self.start()
    self.assertEqual(self.tick(2.7,False,rightBlinker=True,brakePressed=False),[])

  def test_reenable_with_held_signal_does_not_retrigger(self):
    self.start();self.tick(2.7,False,rightBlinker=True)
    for t in [3,5,8]:self.assertEqual(self.tick(t,True,rightBlinker=True),[])
    self.tick(8.1)
    self.assertEqual(self.tick(8.2,leftBlinker=True)[0][0],0x227)

  def test_motion_and_engagement_still_blocked(self):
    for kw in [dict(vEgo=10,vEgoRaw=10,standstill=False,brakePressed=False),dict(gearShifter='park')]:
      self.setUp();self.tick(0,True,**kw);self.tick(2.1,True,**kw)
      self.assertEqual(self.tick(2.2,True,rightBlinker=True,**kw),[])
    self.setUp();self.tick(0);self.tick(2.1)
    active=NS(enabled=True,latActive=True,longActive=True)
    self.assertEqual(self.e.update(2.2,active,out(rightBlinker=True),0,enabled=True),[])

  def test_runtime_polls_setting_and_fails_closed(self):
    param=NS(get_bool=lambda key:True)
    msg=ModuleType('cereal.messaging');msg.sub_sock=lambda *a,**k:object();msg.recv_one_or_none=lambda sock:None
    cereal=ModuleType('cereal');cereal.messaging=msg
    with patch.dict(sys.modules,{'cereal':cereal,'cereal.messaging':msg}):
      runtime=r.SideCameraRuntime()
    self.assertTrue(runtime.available)
    runtime.engine=self.e
    self.start()
    with patch.object(r.time,'monotonic',return_value=2.7), patch.object(r,'read_enabled',side_effect=lambda:param.get_bool(None)):
      runtime.update(CC,out(rightBlinker=True),0)
    self.assertTrue(runtime.enabled)
    param.get_bool=lambda key:False
    with patch.object(r.time,'monotonic',return_value=3.3), patch.object(r,'read_enabled',side_effect=lambda:param.get_bool(None)):
      frames=runtime.update(CC,out(rightBlinker=True),0)
    self.assertFalse(runtime.enabled)
    self.assertEqual([x[0] for x in frames],[0x443,0x227])
    def fail(key):raise OSError('fixture read failure')
    param.get_bool=fail
    with patch.object(r.time,'monotonic',return_value=4.), patch.object(r,'read_enabled',side_effect=lambda:param.get_bool(None)):
      self.assertEqual(runtime.update(CC,out(),0),[])
    self.assertFalse(runtime.enabled)

class StorageTests(unittest.TestCase):
  def test_persistent_round_trip_and_invalid_values(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      path=Path(tmp)/'setting.json'
      self.assertFalse(settings.read_enabled(path))
      settings.write_enabled(True,path);self.assertTrue(settings.read_enabled(path))
      settings.write_enabled(False,path);self.assertFalse(settings.read_enabled(path))
      for text in ['broken','[]','{"enabled": "true"}','{"enabled": 1}']:
        path.write_text(text);self.assertFalse(settings.read_enabled(path))
      with self.assertRaises(TypeError):settings.write_enabled(1,path)

  def test_atomic_failure_preserves_previous_setting(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      path=Path(tmp)/'setting.json';settings.write_enabled(True,path)
      with patch.object(settings.os,'replace',side_effect=OSError('fixture')):
        with self.assertRaises(OSError):settings.write_enabled(False,path)
      self.assertTrue(settings.read_enabled(path))
      self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

class UITests(unittest.TestCase):
  def test_vehicle_toggle_persists_and_refreshes(self):
    import tempfile
    class Toggle:
      def __init__(self,*args,initial_state=False,toggle_callback=None,**kw):
        self.checked=initial_state;self.callback=toggle_callback
      def set_checked(self,v):self.checked=v
      def set_enabled(self,v):self.enabled=v
    class Scroller:
      def __init__(self):self._scroller=self
      def add_widgets(self,items):self.items=items
      def show_event(self):pass
    state=NS(CP=NS(carFingerprint='FORD_F_150_LIGHTNING_MK1'),
             add_offroad_transition_callback=lambda f:None,update_params=lambda:None,
             params=NS(get_bool=lambda key:False))
    with tempfile.TemporaryDirectory() as tmp:
      path=Path(tmp)/'setting.json';settings.write_enabled(True,path)
      modules={
        'openpilot.common.params':NS(Params=lambda:NS()),
        'openpilot.common.swaglog':NS(cloudlog=NS(exception=lambda text:None)),
        'opendbc.car.ford.sidecamera_settings':NS(read_enabled=lambda:settings.read_enabled(path),
                                                 write_enabled=lambda v:settings.write_enabled(v,path)),
        'openpilot.selfdrive.ui.bp.mici.widgets.button_bp':NS(BigParamControlBP=Toggle,BigToggleBP=Toggle),
        'openpilot.selfdrive.ui.bp.mici.widgets.floatbutton':NS(BigParamFloatControl=Toggle),
        'openpilot.selfdrive.ui.ui_state':NS(ui_state=state),
        'openpilot.system.ui.widgets.scroller':NS(NavScroller=Scroller),
      }
      ui=ROOT/'files/selfdrive/ui/bp/mici/layouts/settings/vehicle_mici.py'
      spec=importlib.util.spec_from_file_location('camera_toggle_ui',ui)
      mod=importlib.util.module_from_spec(spec)
      with patch.dict(sys.modules,modules):
        exec(compile('from __future__ import annotations\n'+ui.read_text(),str(ui),'exec'),mod.__dict__)
      first=mod.VehicleLayoutMici();self.assertTrue(first.side_cameras.checked)
      first.side_cameras.callback(False)
      second=mod.VehicleLayoutMici();self.assertFalse(second.side_cameras.checked)
      settings.write_enabled(True,path);second._update_toggles();self.assertTrue(second.side_cameras.checked)
      state.CP.carFingerprint='FORD_EDGE_MK2';self.assertFalse(second._side_cameras_supported())

if __name__=='__main__':unittest.main()
