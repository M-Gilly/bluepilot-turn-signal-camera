#!/usr/bin/env python3
"""Receive-only targeted camera capture. No CAN publisher or arming."""
import argparse,csv,json,sys,time
from pathlib import Path
ROOT=Path('/data/openpilot');sys.path.insert(0,str(ROOT))
def main():
 import cereal.messaging as m
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=35);a=p.parse_args()
 if not 1<=a.seconds<=300:p.error('Choose 1–300 seconds.')
 path=Path('/data')/time.strftime('ford-camera-community-%Y%m%d-%H%M%S.csv')
 sock=m.sub_sock('can',conflate=False,timeout=250)
 states=m.SubMaster(['carState','carControl']);start=time.monotonic();last={}
 print('Listening only. Saved path:',path,flush=True)
 print('Stopped in Drive, brake held, assistance inactive. Signals off, RIGHT, cancel, LEFT, cancel.',flush=True)
 try:
  with path.open('x',newline='') as f:
   writer=csv.writer(f);writer.writerow(['seconds','kind','source','address','payload_or_state'])
   while time.monotonic()-start<a.seconds:
    e=m.recv_one(sock);t=time.monotonic()-start
    if e is not None:
     for frame in e.can:
      src,address,data=int(frame.src),int(frame.address),bytes(frame.dat)
      if address not in (0x227,0x443,0x3ee,0x3a6,0x3a7,0x83):continue
      writer.writerow([round(t,6),'can',src,hex(address),data.hex(' ').upper()])
      key=(src,address)
      if src in (0,2) and last.get(key)!=data:
       print(f'{t:7.3f}s src={src} {address:#05x} {data.hex(" ").upper()}',flush=True);last[key]=data
    states.update(0)
    for name in ['carState','carControl']:
     if not states.updated[name]:continue
     if name=='carState':
      s=states[name];d=dict(valid=bool(states.valid[name]),canValid=bool(s.canValid),gear=str(s.gearShifter),speed=float(s.vEgo),brake=bool(s.brakePressed),gas=bool(s.gasPressed),left=bool(s.leftBlinker),right=bool(s.rightBlinker))
     else:
      s=states[name];d=dict(valid=bool(states.valid[name]),enabled=bool(s.enabled),latActive=bool(s.latActive),longActive=bool(s.longActive))
     writer.writerow([round(t,6),name,'','',json.dumps(d,separators=(',',':'))])
 except KeyboardInterrupt:pass
 print('Saved:',path,flush=True)
if __name__=='__main__':main()
