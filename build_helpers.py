#!/usr/bin/env python3
"""Repair the camera test with forced stock/camera builds and ELF attestation."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time


def build_once(command, root, environment, log):
  process = subprocess.Popen(command, cwd=root, env=environment,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, start_new_session=True)
  try:
    with log.open('w') as stream:
      for line in process.stdout:
        print(line, end='', flush=True)
        stream.write(line)
        stream.flush()
    if process.wait():
      raise RuntimeError('Firmware build failed; see '+str(log))
  finally:
    if process.poll() is None:
      os.killpg(process.pid, signal.SIGTERM)
      try:
        process.wait(timeout=10)
      except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


CAMERA_SYMBOLS = {'ford_cam_requests', 'ford_cam_speed_seen', 'ford_cam_stop_seen', 'ford_cam_trailer_active'}


def read_elf_symbols(elf):
  """Read defined ELF32/ELF64 symbols using Python's standard library only."""
  data = Path(elf).read_bytes()
  if len(data) < 16 or data[:4] != b'\x7fELF' or data[4] not in (1, 2) or data[5] not in (1, 2):
    raise RuntimeError('Not a supported ELF file: '+str(elf))
  endian = '<' if data[5] == 1 else '>'
  is64 = data[4] == 2

  def unpack(fmt, offset):
    length = struct.calcsize(endian+fmt)
    if offset < 0 or offset+length > len(data):
      raise RuntimeError('Truncated ELF structure: '+str(elf))
    return struct.unpack_from(endian+fmt, data, offset)

  shoff = unpack('Q' if is64 else 'I', 40 if is64 else 32)[0]
  entsize, count = unpack('HH', 58 if is64 else 46)
  section_fmt = 'IIQQQQIIQQ' if is64 else 'IIIIIIIIII'
  if not shoff or entsize < struct.calcsize(endian+section_fmt):
    raise RuntimeError('ELF section table is missing or invalid: '+str(elf))
  first = unpack(section_fmt, shoff)
  if count == 0:
    count = first[5]  # Extended ELF section count.
  if count < 1 or shoff+count*entsize > len(data):
    raise RuntimeError('ELF section count exceeds file bounds: '+str(elf))
  sections = [unpack(section_fmt, shoff+i*entsize) for i in range(count)]
  names = set()
  found_table = False
  for section in sections:
    if section[1] not in (2, 11):  # SHT_SYMTAB / SHT_DYNSYM
      continue
    found_table = True
    offset, size, link, stride = section[4], section[5], section[6], section[9]
    symbol_fmt = 'IBBHQQ' if is64 else 'IIIBBH'
    if link >= len(sections) or stride < struct.calcsize(endian+symbol_fmt) or size % stride:
      raise RuntimeError('Invalid ELF symbol table: '+str(elf))
    strings = sections[link]
    start, end = strings[4], strings[4]+strings[5]
    if offset+size > len(data) or end > len(data):
      raise RuntimeError('ELF symbol/string table exceeds file bounds: '+str(elf))
    for pos in range(offset, offset+size, stride):
      symbol = unpack(symbol_fmt, pos)
      name, defined = symbol[0], symbol[3 if is64 else 5]
      if not name or not defined:
        continue
      if name >= strings[5]:
        raise RuntimeError('Invalid ELF symbol name offset: '+str(elf))
      terminator = data.find(b'\0', start+name, end)
      if terminator < 0:
        raise RuntimeError('Unterminated ELF symbol name: '+str(elf))
      names.add(data[start+name:terminator].decode('utf-8', errors='replace'))
  if not found_table:
    raise RuntimeError('ELF has no symbol table: '+str(elf))
  return names


def firmware_symbols(root, firmware, environment, tools):
  return read_elf_symbols(firmware.parent/'panda_h7/main.elf')

