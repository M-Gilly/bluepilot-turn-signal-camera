"""BluePilot MICI: Vehicle settings panel — cluster UI, 12V battery limit."""

from collections.abc import Callable

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from opendbc.car.ford.sidecamera_settings import read_enabled, write_enabled
from openpilot.selfdrive.ui.bp.mici.widgets.button_bp import BigParamControlBP, BigToggleBP
from openpilot.selfdrive.ui.bp.mici.widgets.floatbutton import BigParamFloatControl
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.scroller import NavScroller


class VehicleLayoutMici(NavScroller):
  def __init__(self, back_callback: Callable[[], None] | None = None):
    super().__init__()
    if back_callback is not None:
      self.set_back_callback(back_callback)
    self._params = Params()

    self.show_hands_free_ui = BigParamControlBP("Show BlueCruise UI on Cluster", "send_hands_free_cluster_msg")
    # Init-time param (read once at car init, mirrored into panda safety); takes effect after restart.
    # FORD_EDGE_MK2's pinion sensor only reports a relative angle -- the safety/control
    # layers already no-op this toggle there, so grey it out too (see values_ext.py
    # FORD_PINION_GEOMETRY_INDEX).
    self.steer_angle_curvature = BigParamControlBP("Use Pinion Yaw Sensor", "FordPrefSteerAngleCurvature")
    self.steer_angle_curvature.set_enabled(self._pinion_yaw_sensor_supported)
    self.side_cameras = BigToggleBP("Turn Signal Blind Spot View", initial_state=read_enabled(),
                                    toggle_callback=self._set_side_cameras)
    self.side_cameras.set_enabled(self._side_cameras_supported)
    self.vbatt_pause_charging = BigParamFloatControl("12V Battery Limit", "vbatt_pause_charging", min=11.0, max=14.0, step=0.1)

    self._scroller.add_widgets([
      self.show_hands_free_ui,
      self.steer_angle_curvature,
      self.side_cameras,
      self.vbatt_pause_charging,
    ])

    self._refresh_toggles = (
      ("send_hands_free_cluster_msg", self.show_hands_free_ui),
      ("FordPrefSteerAngleCurvature", self.steer_angle_curvature),
    )

    ui_state.add_offroad_transition_callback(self._update_toggles)

  @staticmethod
  def _pinion_yaw_sensor_supported() -> bool:
    return ui_state.CP is None or ui_state.CP.carFingerprint != "FORD_EDGE_MK2"

  @staticmethod
  def _side_cameras_supported() -> bool:
    return ui_state.CP is None or ui_state.CP.carFingerprint == "FORD_F_150_LIGHTNING_MK1"

  def _set_side_cameras(self, enabled: bool):
    try:
      write_enabled(enabled)
    except OSError:
      cloudlog.exception("Could not save side camera setting")
    self.side_cameras.set_checked(read_enabled())

  def show_event(self):
    super().show_event()
    self._update_toggles()

  def _update_toggles(self):
    self.side_cameras.set_checked(read_enabled())
    ui_state.update_params()
    for key, item in self._refresh_toggles:
      item.set_checked(ui_state.params.get_bool(key))
