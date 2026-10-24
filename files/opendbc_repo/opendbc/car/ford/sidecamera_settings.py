"""Persistent preference shared by the camera runtime and Python settings UI."""
import json
import os
from pathlib import Path
import tempfile

SETTINGS_PATH = Path('/data/ford-sidecamera-settings.json')


def read_enabled(path=SETTINGS_PATH):
  try:
    data = json.loads(Path(path).read_text())
    return isinstance(data, dict) and data.get('enabled') is True
  except (OSError, ValueError, TypeError):
    return False


def write_enabled(enabled, path=SETTINGS_PATH):
  if type(enabled) is not bool:
    raise TypeError('Camera setting must be a boolean.')
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
  tmp = Path(name)
  try:
    with os.fdopen(fd, 'w') as stream:
      json.dump({'enabled': enabled}, stream)
      stream.write('\n')
      stream.flush()
      os.fsync(stream.fileno())
    tmp.chmod(0o644)
    os.replace(tmp, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
      os.fsync(directory_fd)
    finally:
      os.close(directory_fd)
  finally:
    tmp.unlink(missing_ok=True)
