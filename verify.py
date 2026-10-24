#!/usr/bin/env python3
"""Offroad verification; no arming, CAN transmission or firmware changes."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path('/data/openpilot');HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def main():
 import cereal.messaging as m
 sock=m.sub_sock('deviceState',conflate=True,timeout=3000);e=m.recv_one(sock)
 if e is None or not e.valid or e.deviceState.started or not 0<=time.monotonic()-e.logMonoTime/1e9<3:
  raise RuntimeError('Truck must be OFF, comma powered on offroad screen.')
 manifest=json.loads((HERE/'manifest.json').read_text());ok=True
 for rel,entry in manifest.items():
  p=ROOT/rel;match=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==entry['installed']
  print(('MATCH: ' if match else 'DIFFERENT: ')+rel);ok &= match
 receipt=HERE/'installation.json'
 if not receipt.exists():raise RuntimeError('No receipt from this community installer. Earlier private beta users should retain their original verification/restore tools.')
 r=json.loads(receipt.read_text());f=ROOT/'panda/board/obj/panda_h7.bin.signed'
 match=r.get('state')=='installed' and hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256']
 print('Saved firmware matches installed receipt:',match);ok &= match
 from opendbc.car.ford.sidecamera_runtime import LengthAttempt
 from opendbc.car.ford.sidecamera_settings import read_enabled
 print('Python import OK; toggle:',read_enabled())
 if not (ROOT/'prebuilt').is_file():raise RuntimeError('Startup rebuild marker missing.')
 from panda import Panda
 # Low-level read only. Do NOT construct Panda(): its constructor changes
 # communications configuration. No safety mode changes or resets here.
 ctx,handle,serial,bootstub=Panda.spi_connect(None)
 if handle is None:raise RuntimeError('Internal SPI Panda unavailable; running firmware NOT verified.')
 try:
  if bootstub:raise RuntimeError('Panda is in bootstub.')
  signature=bytes(handle.controlRead(Panda.REQUEST_IN,0xd3,0,0,64)+handle.controlRead(Panda.REQUEST_IN,0xd4,0,0,64))
  match=signature==Panda.get_signature_from_firmware(str(f));print('RUNNING Panda signature matches:',match);ok &= match
 finally:handle.close()
 if not ok:raise RuntimeError('Verification incomplete or mismatch. Keep toggle OFF and report output.')
 print('VERIFIED: installed sources and running Panda match. This is not validation of receiver detection performance.')
if __name__=='__main__':
 try:main()
 except Exception as e:print('STOP:',e,file=sys.stderr);sys.exit(2)
