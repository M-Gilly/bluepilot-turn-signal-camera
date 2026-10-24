"""Bounded length-only camera experiment through the existing Ford sender."""
import time
from opendbc.car.ford.sidecamera_engine import eligible
from opendbc.car.ford.sidecamera_settings import read_enabled

LENGTH_ID = 0x227
TRAILER_ID = 0x443
LENGTH_BASE = bytes.fromhex('00 00 FC 00 80 00 FC 40')
TRAILER_BASES = (bytes.fromhex('00 00 00 FF FC 00 00 00'),
                 bytes.fromhex('00 00 10 FF FC 00 00 00'))


class LengthAttempt:
  def __init__(self):
    self.samples = {}
    self.stable_since = None
    self.last_direction = 0
    self.ready = False
    self.active = False
    self.until = 0.
    self.cooldown = 0.
    self.connect_at = 0.
    self.next_length = 0.
    self.next_trailer = 0.
    self.trailer_sent = False

  def observe(self, now, bus, address, data):
    if bus == 0 and address in (LENGTH_ID, TRAILER_ID) and len(data) == 8:
      self.samples[address] = (now, data)

  def fresh(self, now, address):
    sample = self.samples.get(address)
    if sample is not None and 0 <= now-sample[0] < 1.5:
      return sample[1]
    return None

  def update(self, now, CC, out, bus, enabled=True):
    safe = eligible(CC, out, bus, True)
    direction = 1 if out.leftBlinker else 2 if out.rightBlinker else 0
    length = self.fresh(now, LENGTH_ID)
    trailer = self.fresh(now, TRAILER_ID)
    known = length == LENGTH_BASE and trailer in TRAILER_BASES
    if not safe:
      self.active = self.ready = False
      self.stable_since = None
      self.last_direction = direction
      self.cooldown = max(self.cooldown, now+2.)
      return []  # Native leases expire; never send after losing eligibility.
    if self.stable_since is None:
      self.stable_since = now
    if self.active and (not enabled or not known or direction != self.last_direction or now >= self.until):
      self.active = self.ready = False
      self.cooldown = now+2.
      self.last_direction = direction
      frames = []
      # Relinquish only the fields still known to belong to this attempt.
      if trailer in TRAILER_BASES and self.trailer_sent:
        frames.append((TRAILER_ID, trailer, 2))
      if length == LENGTH_BASE:
        frames.append((LENGTH_ID, length, 2))
      self.trailer_sent = False
      return frames
    if not self.active:
      if not enabled:
        self.ready = False
        self.last_direction = direction
        return []
      if direction == 0 and now >= self.cooldown and now-self.stable_since >= 2.:
        self.ready = True
      rising = direction != 0 and self.last_direction == 0
      self.last_direction = direction
      if not (rising and self.ready and known):
        if direction:
          self.ready = False
        return []
      self.active = True
      self.ready = False
      self.until = now+8.
      self.connect_at = now+.35
      self.next_length = now
      self.next_trailer = self.connect_at
      self.trailer_sent = False
    frames = []
    if now >= self.next_length:
      # Captured short-profile raw field; no inferred conversion from feet.
      patched = length[:6]+bytes((0x12 | (length[6] & 1),))+length[7:]
      frames.append((LENGTH_ID, patched, 2))
      self.next_length = now+1.
    if now >= self.next_trailer:
      frames.append((TRAILER_ID, bytes((trailer[0] | 0x80,))+trailer[1:], 2))
      self.trailer_sent = True
      self.next_trailer = now+1.
    return frames


class SideCameraRuntime:
  def __init__(self):
    self.engine = LengthAttempt()
    self.available = False
    self.enabled = False
    self.next_settings_read = 0.
    try:
      import cereal.messaging as messaging
      self.messaging = messaging
      self.can = messaging.sub_sock('can', conflate=False)
      self.available = True
    except Exception:
      pass

  def update(self, CC, out, bus):
    if not self.available:
      return []
    now = time.monotonic()
    try:
      for _ in range(25):
        event = self.messaging.recv_one_or_none(self.can)
        if event is None:
          break
        if not 0 <= now-int(event.logMonoTime)/1e9 < .5:
          continue
        for frame in event.can:
          self.engine.observe(now, int(frame.src), int(frame.address), bytes(frame.dat))
      if now >= self.next_settings_read:
        try:
          self.enabled = read_enabled()
        except Exception:
          self.enabled = False
        self.next_settings_read = now+.5
      return self.engine.update(now, CC, out, bus, enabled=self.enabled)
    except Exception:
      self.engine.active = False
      self.available = False
      return []
