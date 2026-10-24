"""Finite stationary turn-signal camera experiments; no CAN I/O here."""
import math

VIEW_ID = 0x3E2
BUTTON_ID = 0x192
TRAILER_ID = 0x443
TRAILER_BASE = bytes.fromhex('00 00 10 FF FE 00 00 00')
TRAILER_ON = bytes.fromhex('80 00 10 FF FE 00 00 00')
TRAILER_FACTORY = bytes.fromhex('84 00 10 FF FE 00 00 00')
FACTORY_VIEWS = (7, 0x2C, 0x0B, 0x26)


def view_request(value):
  return (VIEW_ID, bytes((0, value, 8, 0x1B, 0x81, 0x50, 0, 0)), 0)


def button(pressed):
  return (BUTTON_ID, bytes((0, int(pressed), 0, 0, 0, 0, 0, 0)), 0)


def eligible(CC, out, bus, stationary_drive=False):
  try:
    gear_ok = (str(out.gearShifter) == 'drive' and out.brakePressed and not out.gasPressed) if stationary_drive else str(out.gearShifter) == 'park'
    return (bus == 0 and out.canValid and out.standstill and gear_ok and
            all(math.isfinite(float(v)) and abs(float(v)) < .05 for v in (out.vEgo, out.vEgoRaw)) and
            not (out.leftBlinker and out.rightBlinker) and
            not CC.enabled and not CC.latActive and not CC.longActive)
  except (AttributeError, TypeError, ValueError):
    return False


class Engine:
  def __init__(self):
    self.view = None
    self.view_at = -1e9
    self.trailer = None
    self.trailer_at = -1e9
    self.strategy = 'direct'
    self.stationary_drive = False
    self.until = 0.
    self.phase = 'disabled'
    self.detail = 'Not armed.'
    self.target = None
    self.original = None
    self.deadline = 0.
    self.clear_at = None
    self.virtual = False
    self.virtual_payload = TRAILER_ON
    self.virtual_started = 0.
    self.next_trailer = 0.
    self.sent_view_at = -1e9
    self.last_direction = 0
    self.woke = False
    self.blocked = False
    self.eligible_since = None
    self.attempts = 0
    self.last_restore_at = -1e9

  def observe(self, now, bus, address, data):
    if bus == 2 and address == 0x3EE and len(data) == 8 and data[2:4] == b'\x08\x1b':
      self.view = int.from_bytes(data[:2], 'big')
      self.view_at = now
    elif bus == 0 and address == TRAILER_ID and len(data) == 8:
      self.trailer, self.trailer_at = data, now

  def arm(self, now, strategy, seconds, stationary_drive=False):
    if strategy == 'trailer-auto' and not stationary_drive:
      raise ValueError('Trailer-auto requires stationary Drive with brake held.')
    if self.phase not in ('disabled', 'idle', 'failed') or self.clear_at is not None or self.virtual:
      raise ValueError('Another attempt or cleanup is active.')
    if strategy not in ('direct', 'wake', 'trailer', 'trailer-factory', 'trailer-auto') or not 3 <= seconds <= 25:
      raise ValueError('Invalid fixed strategy or duration.')
    if type(stationary_drive) is not bool or (stationary_drive and strategy not in ('direct', 'trailer-auto')):
      raise ValueError('Stationary Drive supports direct or trailer-auto only.')
    self.strategy = strategy
    if self.stationary_drive != stationary_drive:
      self.eligible_since = None
    self.stationary_drive = stationary_drive
    self.virtual_payload = TRAILER_FACTORY if strategy == 'trailer-factory' else TRAILER_ON
    self.until = now + seconds
    self.phase = 'idle'
    self.target = None
    self.last_direction = 0
    self.attempts = 0
    self.blocked = False
    self.detail = ('Armed stopped in Drive; keep foot brake held. ' if stationary_drive else 'Armed in Park; ') + 'Use one physical turn signal. Video requires visual confirmation.'

  def disarm(self):
    self.until = 0.

  def _fresh_view(self, now):
    return now-self.view_at < 2.2

  def _restore(self, now):
    frames = []
    if self.virtual:
      # Only send a captured baseline if it is still the genuine current state.
      # Otherwise relinquish the forwarding lease; the next genuine frame wins.
      if now-self.trailer_at < 1.5 and self.trailer == TRAILER_BASE:
        frames.append((TRAILER_ID, TRAILER_BASE, 2))
      self.virtual = False
    # Never toggle a camera that the user has since changed to a different view.
    if self._fresh_view(now) and self.view in (self.target, 7 if self.woke else -1):
      if self.original == 0 and self.woke and self.clear_at is None:
        frames.append(button(True))
        self.clear_at = now + .5
        self.detail = 'Closing the camera opened by this attempt.'
      elif self.original in FACTORY_VIEWS and self.view != self.original:
        frames.append(view_request(self.original))
        self.last_restore_at = now
    self.target = None
    self.woke = False
    return frames

  def _request_side(self, now):
    self.phase = 'waiting'
    self.sent_view_at = now
    self.deadline = now + 2.5
    self.detail = 'View request queued once; waiting for genuine bus-2 state. Check video separately.'
    return [view_request(self.target)]

  def update(self, now, CC, out, bus):
    if self.strategy == 'trailer-auto':
      return self._update_trailer_auto(now, CC, out, bus)
    frames = []
    safe = eligible(CC, out, bus, self.stationary_drive)
    if not safe:
      self.eligible_since = None
      self.until = 0.
      self.phase = 'disabled'
      self.target = None
      self.virtual = False
      self.clear_at = None
      self.woke = False
      self.detail = 'Stopped: required gear/brake, valid CAN, speed, hazards or inactive-assistance check failed. No new output.'
      return []
    if self.eligible_since is None:
      self.eligible_since = now
    stable = now-self.eligible_since >= 2.
    if self.clear_at is not None and now >= self.clear_at:
      frames.append(button(False))
      self.clear_at = None
    direction = 1 if out.leftBlinker else 2 if out.rightBlinker else 0
    active = now < self.until
    if not active:
      if self.target is not None or self.virtual:
        frames.extend(self._restore(now))
      self.phase = 'disabled'
      self.last_direction = direction
      return frames
    if not stable:
      return frames
    if self.target is not None and direction != self.last_direction:
      frames.extend(self._restore(now))
      self.phase = 'idle'
      # Wait for a subsequent rising edge, rather than racing a direction change
      # against a restore or a still-held camera-button pulse.
      self.last_direction = direction
      self.detail = 'Previous attempt ended; release the signal before selecting the next direction.'
      return frames
    if self.virtual:
      if self.trailer != TRAILER_BASE or now-self.trailer_at >= 1.5 or now-self.virtual_started >= 8.:
        frames.extend(self._restore(now))
        self.phase = 'failed'
        self.detail = 'Trailer fallback ended: eight-second limit or genuine trailer status changed/staled.'
        return frames
      if now >= self.next_trailer:
        frames.append((TRAILER_ID, self.virtual_payload, 2))
        self.next_trailer = now + 1.
    if self.phase == 'warming' and now >= self.deadline:
      if self._fresh_view(now) and self.view == self.target:
        self.phase = 'holding'
        self.detail = 'Matching state appeared through trailer-mode logic. Confirm actual video.'
      else:
        frames.extend(self._request_side(now))
    elif self.phase == 'opening':
      if self.clear_at is None and self._fresh_view(now) and self.view in FACTORY_VIEWS:
        frames.extend(self._request_side(now))
      elif now >= self.deadline:
        self.phase = 'failed'
        self.detail = 'Camera wake did not produce a supported view; no guessed retries. Close manually if needed.'
    elif self.phase == 'waiting':
      if self._fresh_view(now) and self.view_at >= self.sent_view_at and self.view == self.target:
        self.phase = 'holding'
        self.detail = 'Matching state received; this does not verify video. Confirm actual mirror feed.'
      elif now >= self.deadline:
        self.phase = 'failed'
        self.detail = 'No matching camera state. No automatic strategy escalation or retry.'
    elif self.phase == 'holding' and self._fresh_view(now) and self.view != self.target:
      frames.extend(self._restore(now))
      self.phase = 'failed'
      self.detail = 'Camera state changed outside this attempt; relinquishing control.'
    if self.phase in ('idle', 'failed') and direction and direction != self.last_direction:
      if self.clear_at is not None or now-self.last_restore_at < .3:
        self.last_direction = direction
        self.detail = 'Cleanup still active; release the signal and try again.'
        return frames
      limit = 2 if self.strategy == 'direct' else 1
      if self.attempts >= limit or not self._fresh_view(now):
        self.detail = 'Attempt budget or fresh camera-state check failed; disarm and review the recording.'
        self.last_direction = direction
        return frames
      target = 0x2F if direction == 1 else 0x30
      if self.stationary_drive and self.view == target:
        self.target, self.original = target, self.view
        self.attempts += 1
        self.phase = 'holding'
        self.detail = 'Matching side state already appeared; no request sent. Confirm actual video.'
        self.last_direction = direction
        return frames
      if self.view not in (0,) + FACTORY_VIEWS:
        self.detail = 'Unknown initial view; open the factory front view before testing.'
        self.last_direction = direction
        return frames
      if self.strategy == 'direct' and self.view == 0:
        self.detail = 'Direct mode requires the factory camera already open. Use wake mode separately.'
        self.last_direction = direction
        return frames
      if self.strategy.startswith('trailer') and (now-self.trailer_at >= 1.5 or self.trailer is None):
        self.detail = 'No fresh genuine trailer status; trailer experiment refused.'
        self.last_direction = direction
        return frames
      if self.strategy.startswith('trailer') and self.trailer != TRAILER_BASE and not (self.trailer[0] & 0x80):
        self.detail = 'Unrecognized trailer payload; refusing to invent or overwrite other fields.'
        self.last_direction = direction
        return frames
      self.target, self.original = target, self.view
      self.attempts += 1
      self.woke = False
      if self.strategy.startswith('trailer') and self.trailer == TRAILER_BASE:
        frames.append((TRAILER_ID, self.virtual_payload, 2))
        self.virtual = True
        self.virtual_started = now
        self.next_trailer = now + 1.
        self.deadline = now + 2.
        self.phase = 'warming'
        self.detail = 'Explicit trailer experiment: camera-side network only, maximum eight seconds.'
      elif self.original == 0 and self.strategy == 'wake':
        frames.append(button(True))
        self.clear_at = now + .5
        self.deadline = now + 2.
        self.phase = 'opening'
        self.woke = True
        self.detail = 'One bounded factory-style button pulse; waiting for camera entry.'
      else:
        frames.extend(self._request_side(now))
    self.last_direction = direction
    return frames

  def _update_trailer_auto(self, now, CC, out, bus):
    # Isolated experiment: never issue a view request or a camera-button pulse.
    baseline = self.trailer
    known_baselines = (bytes.fromhex('00 00 00 FF FC 00 00 00'),
                       bytes.fromhex('00 00 10 FF FC 00 00 00'))
    direction = 1 if out.leftBlinker else 2 if out.rightBlinker else 0
    if not eligible(CC, out, bus, True):
      self.until = 0.
      self.virtual = False
      self.target = None
      self.eligible_since = None
      self.phase = 'disabled'
      self.detail = 'Stopped: Drive/brake/zero-speed/inactive-controls requirement lost. Normal forwarding resumes.'
      return []
    if self.eligible_since is None:
      self.eligible_since = now
    fresh = baseline in known_baselines and now-self.trailer_at < 1.5
    if self.virtual:
      ended = now >= self.until or now-self.virtual_started >= 8. or direction != self.last_direction or not fresh
      if ended:
        self.virtual = False
        self.until = 0.
        self.target = None
        self.phase = 'disabled'
        self.detail = 'Trailer-only test ended; no view command sent. Normal trailer forwarding resumes.'
        return [(TRAILER_ID, baseline, 2)] if fresh else []
      if self._fresh_view(now) and self.view_at >= self.virtual_started and self.view == self.target:
        self.phase = 'holding'
        self.detail = 'Genuine side state observed during trailer-only test. Confirm the actual video.'
      if now >= self.next_trailer:
        self.next_trailer = now + 1.
        return [(TRAILER_ID, bytes((baseline[0] | 0x80,)) + baseline[1:], 2)]
      return []
    if now >= self.until:
      self.phase = 'disabled'
      return []
    if now-self.eligible_since < 2.:
      self.last_direction = direction
      return []
    if direction and direction != self.last_direction and not self.attempts:
      self.last_direction = direction
      if not fresh:
        self.until = 0.
        self.phase = 'failed'
        self.detail = 'Fresh exact current disconnected trailer payload not verified; no output.'
        return []
      self.attempts = 1
      self.target = 0x2F if direction == 1 else 0x30
      self.virtual = True
      self.virtual_started = now
      self.next_trailer = now + 1.
      self.phase = 'warming'
      self.detail = 'Trailer connection bit only, camera bus only, at most eight seconds. No camera-view requests.'
      return [(TRAILER_ID, bytes((baseline[0] | 0x80,)) + baseline[1:], 2)]
    self.last_direction = direction
    return []
