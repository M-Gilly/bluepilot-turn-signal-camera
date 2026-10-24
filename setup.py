#!/usr/bin/env python3
"""Pinned, stationary-only community beta installer. No CAN publisher."""
import argparse, ast, fcntl, hashlib, json, os, shutil, struct, subprocess, sys, tempfile, time
from pathlib import Path
from build_helpers import build_once, read_elf_symbols
ROOT=Path('/data/openpilot')
HERE=Path(__file__).resolve().parent
BLUEPILOT='e1d051d7ba270261b4455068bd68f1a58db15a4a'
PANDA='d994e8e8009d934a94c3a94c863b559118353bdd'
FIRMWARE=ROOT/'panda/board/obj/panda_h7.bin.signed'
SETTING=Path('/data/ford-sidecamera-settings.json')
BACKUPS=Path('/data/ford-community-camera-backups')
MANIFEST=json.loads((HERE/'manifest.json').read_text())

def sha(data):return hashlib.sha256(data).hexdigest()
def digest(path):return sha(path.read_bytes()) if path.exists() else None

def atomic(path,data,mode=None):
  path.parent.mkdir(parents=True,exist_ok=True)
  if path.is_symlink():raise RuntimeError('Refusing file symlink: '+str(path))
  mode=mode if mode is not None else (path.stat().st_mode & 0o777 if path.exists() else 0o644)
  fd,name=tempfile.mkstemp(prefix=path.name+'.camera-',dir=path.parent)
  try:
    with os.fdopen(fd,'wb') as stream:
      stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chmod(name,mode);os.replace(name,path)
  finally:
    if os.path.exists(name):os.unlink(name)

def package_check():
  for rel,entry in MANIFEST.items():
    p=HERE/'files'/rel
    if p.is_symlink() or digest(p)!=entry['installed']:raise RuntimeError('Package checksum mismatch: '+rel)
    if p.suffix=='.py':ast.parse(p.read_text())

def revisions():
  for path,expected in [(ROOT,BLUEPILOT),(ROOT/'panda',PANDA)]:
    if subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()!=expected:
      raise RuntimeError('Unsupported revision: '+str(path))

def offroad():
  sys.path.insert(0,str(ROOT))
  import cereal.messaging as m
  sock=m.sub_sock('deviceState',conflate=True,timeout=3000);e=m.recv_one(sock)
  if e is None or not e.valid or e.deviceState.started or not 0<=time.monotonic()-e.logMonoTime/1e9<3:
    raise RuntimeError('Truck must be OFF, comma powered on its offroad screen.')

def vehicle_check():
  sys.path.insert(0,str(ROOT))
  from openpilot.common.params import Params
  from cereal import car
  data=Params().get('CarParamsPersistent')
  if not data:raise RuntimeError('No stored vehicle identification. Configure and identify the truck first.')
  with car.CarParams.from_bytes(data) as cp:
    if cp.carFingerprint!='FORD_F_150_LIGHTNING_MK1':raise RuntimeError('Only FORD_F_150_LIGHTNING_MK1 is supported.')

def installed_sources():
  return all(digest(ROOT/rel)==e['installed'] for rel,e in MANIFEST.items())

def check_stock():
  package_check();revisions()
  for rel,e in MANIFEST.items():
    p=ROOT/rel
    if p.is_symlink() or digest(p)!=e['stock']:raise RuntimeError('Expected exact stock source: '+rel+'; do not reset files to force this check.')
  # No additional tracked safety/Panda changes are allowed in the build inputs.
  for directory,paths in [(ROOT,['opendbc_repo/opendbc/safety']),(ROOT/'panda',[])]:
    args=['git','-C',str(directory),'status','--porcelain','--untracked-files=all']
    if paths:args+=['--']+paths
    if subprocess.check_output(args,text=True).strip():raise RuntimeError('Unrelated safety/Panda changes exist.')
  if not FIRMWARE.is_file() or FIRMWARE.is_symlink():raise RuntimeError('Existing Panda firmware artifact missing or symlinked.')
  if (ROOT/'prebuilt').is_symlink() or SETTING.is_symlink():raise RuntimeError('Unexpected marker/settings symlink.')
  for tool in ['git','tar','scons','arm-none-eabi-gcc']:
    if not shutil.which(tool,path=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')):raise RuntimeError('Missing existing build tool: '+tool)
  from Crypto.PublicKey import RSA
  vehicle_check()

def status():
  package_check();revisions()
  if installed_sources():
    receipt=HERE/'installation.json'
    if receipt.exists():
      r=json.loads(receipt.read_text())
      if r.get('state')=='installed' and digest(FIRMWARE)==r.get('sha256'):
        print('ALREADY INSTALLED: sources and saved firmware match. No reinstall needed.');return
    print('Source matches this beta, but no matching local install receipt/firmware. Keep the earlier installer for rollback; do not reinstall over it.');return
  check_stock();offroad();print('READY: exact supported stock files, vehicle and build tools verified. No source changes made.')

def verify_signed(firmware, raw, public_key):
  from Crypto.PublicKey import RSA
  signed = firmware.read_bytes()
  binary = raw.read_bytes()
  body = struct.pack('<I', len(binary)+8)+binary[4:]+b'VERS'+struct.pack('<I', 2)
  if len(signed) != len(body)+128 or signed[:-128] != body:
    raise RuntimeError('Signed artifact does not match freshly linked binary.')
  key = RSA.import_key(public_key.read_bytes())
  digest = hashlib.sha1(body[4:]).digest()
  expected = b'\x00\x01'+b'\xff'*0x69+b'\x00'+digest
  signature = pow(int.from_bytes(signed[-128:], 'big'), key.e, key.n).to_bytes(128, 'big')
  if signature != expected:
    raise RuntimeError('Firmware signature verification failed.')

def prepare():
  check_stock()
  offroad()
  baseline_firmware = digest(FIRMWARE)
  stage = Path(tempfile.mkdtemp(prefix='ford-community-build-', dir='/data'))
  sdk = stage/'sdk'
  shutil.copytree(ROOT/'opendbc_repo/opendbc/safety', sdk/'opendbc/safety')
  (sdk/'opendbc/__init__.py').write_text('from pathlib import Path\nINCLUDE_PATH = str(Path(__file__).resolve().parents[1])\n')
  for rel, entry in MANIFEST.items():
    if '/safety/' in rel:
      destination = sdk/Path(rel).relative_to('opendbc_repo')
      destination.write_bytes((HERE/'files'/rel).read_bytes())
  tree = stage/'panda'
  tree.mkdir()
  archive = stage/'panda.tar'
  with archive.open('wb') as stream:
    subprocess.run(['git', '-C', str(ROOT/'panda'), 'archive', 'HEAD'], stdout=stream, check=True)
  subprocess.run(['tar', '-xf', str(archive), '-C', str(tree)], check=True)
  gitdir = subprocess.check_output(['git', '-C', str(ROOT/'panda'), 'rev-parse', '--absolute-git-dir'], text=True).strip()
  (tree/'.git').write_text('gitdir: '+gitdir+'\n')
  env = os.environ.copy()
  env['PYTHONPATH'] = str(sdk)+os.pathsep+str(ROOT)
  env['PATH'] = str(Path(sys.executable).parent)+os.pathsep+env.get('PATH', '')
  env['PWD'] = str(tree)
  include = subprocess.check_output([sys.executable, '-c', 'import opendbc; print(opendbc.INCLUDE_PATH)'], cwd=tree, env=env, text=True).strip()
  if Path(include).resolve() != sdk.resolve():
    raise RuntimeError('Isolated safety source is not selected.')
  scons = shutil.which('scons', path=env['PATH'])
  if not scons or not shutil.which('arm-none-eabi-gcc', path=env['PATH']):
    raise RuntimeError('Existing firmware build tools are unavailable.')
  artifact = tree/'board/obj/panda_h7.bin.signed'
  print('Building separate tree:', stage, flush=True)
  build_once([scons, '--cache-disable', '--implicit-deps-changed', '-C', str(tree), '-j2', str(artifact)], tree, env, stage/'build.log')
  symbols = read_elf_symbols(tree/'board/obj/panda_h7/main.elf')
  required = {'ford_cam_length_active', 'ford_cam_length_frames', 'ford_cam_trailer_active', 'ford_cam_speed_seen'}
  if not required.issubset(symbols):
    raise RuntimeError('Length-test code is missing from the linked ELF.')
  verify_signed(artifact, tree/'board/obj/panda_h7/main.bin', tree/'board/certs/debug.pub')
  check_stock()
  record = dict(stage=str(stage), firmware=str(artifact), sha256=sha(artifact.read_bytes()),
                baseline_firmware=baseline_firmware, files=MANIFEST, symbols=sorted(required), bluepilot=BLUEPILOT, panda=PANDA)
  atomic(HERE/'prepared.json', json.dumps(record, indent=2).encode())
  print('PREPARED. Installed source and firmware were not changed.', flush=True)
  print('Verified firmware SHA256:', record['sha256'], flush=True)

def backup_paths():
  return {rel:ROOT/rel for rel in MANIFEST}|{'@firmware':FIRMWARE,'@prebuilt':ROOT/'prebuilt','@settings':SETTING}

def snapshot():
  BACKUPS.mkdir(exist_ok=True)
  backup=Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'),dir=BACKUPS))
  entries={}
  for i,(key,path) in enumerate(backup_paths().items()):
    data=path.read_bytes() if path.exists() else None
    name=str(i)+'.saved' if data is not None else None
    if data is not None:atomic(backup/name,data)
    entries[key]=dict(saved=name,sha256=sha(data) if data is not None else None,mode=path.stat().st_mode & 0o777 if data is not None else None)
  return dict(backup=str(backup),entries=entries)

def restore_record(record):
  backup=Path(record['backup']).resolve()
  if backup.parent!=BACKUPS.resolve():raise RuntimeError('Unexpected backup directory.')
  values=[]
  for key,path in backup_paths().items():
    entry=record['entries'][key]
    data=(backup/entry['saved']).read_bytes() if entry['saved'] else None
    if data is not None and sha(data)!=entry['sha256']:raise RuntimeError('Backup checksum mismatch: '+key)
    if path.is_symlink():raise RuntimeError('Refusing restore over symlink: '+key)
    values.append((path,data,entry['mode']))
  for path,data,mode in values:
    if data is None:path.unlink(missing_ok=True)
    else:atomic(path,data,mode)
  atomic(HERE/'installation.json',json.dumps(dict(record,state='restored'),indent=2).encode())

def deploy():
  if installed_sources():status();return
  check_stock();offroad()
  prepared=json.loads((HERE/'prepared.json').read_text())
  if prepared['files']!=MANIFEST or prepared['bluepilot']!=BLUEPILOT or prepared['panda']!=PANDA:
    raise RuntimeError('Prepared artifact belongs to another package.')
  artifact=Path(prepared['firmware'])
  if digest(artifact)!=prepared['sha256']:raise RuntimeError('Prepared firmware changed.')
  if digest(FIRMWARE)!=prepared['baseline_firmware']:raise RuntimeError('Baseline firmware changed after preparation.')
  prior=HERE/'installation.json'
  if prior.exists() and json.loads(prior.read_text()).get('state') not in ('restored',):
    raise RuntimeError('Existing install/recovery receipt present. Restore or inspect it first.')
  record=dict(prepared,**snapshot(),state='backed-up')
  atomic(HERE/'installation.json',json.dumps(record,indent=2).encode())
  try:
    offroad()
    for rel in MANIFEST:atomic(ROOT/rel,(HERE/'files'/rel).read_bytes())
    atomic(FIRMWARE,artifact.read_bytes())
    if not (ROOT/'prebuilt').exists():atomic(ROOT/'prebuilt',b'')
    atomic(SETTING,b'{"enabled": false}\n')
    if not installed_sources() or digest(FIRMWARE)!=record['sha256']:raise RuntimeError('Installed checksum mismatch.')
    # Fresh interpreter checks the actual installed Python imports.
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT);env['PWD']=str(ROOT)
    subprocess.run([sys.executable,'-c','from opendbc.car.ford.sidecamera_runtime import LengthAttempt; from opendbc.car.ford.sidecamera_settings import read_enabled; assert read_enabled() is False'],cwd=ROOT,env=env,check=True)
    atomic(HERE/'installation.json',json.dumps(dict(record,state='installed'),indent=2).encode())
  except BaseException:
    restore_record(record);raise
  print('INSTALLED, default OFF. Backup:',record['backup'])
  print('Reboot once. Then use BluePilot > Vehicle > Turn Signal Blind Spot View.')
  print('Stopped Drive + brake held + assistance inactive only. Startup rebuild/staged activation paused until restore.')

def restore():
  revisions();offroad()
  r=json.loads((HERE/'installation.json').read_text())
  if r.get('state')=='restored':print('Already restored.');return
  # Accept a completed deployment or a mix left by an interrupted deployment.
  for rel,e in MANIFEST.items():
    old=r['entries'][rel]['sha256']
    if digest(ROOT/rel) not in (old,e['installed']):raise RuntimeError('Newer local source changes exist: '+rel)
  if digest(FIRMWARE) not in (r['sha256'],r['entries']['@firmware']['sha256']):raise RuntimeError('Newer firmware artifact exists.')
  restore_record(r)
  print('Previous sources, firmware, startup files and preference restored. Reboot once.')

def main():
  p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check','prepare','deploy','restore'])
  args=p.parse_args()
  # Preserve device-local receipts in a stable installation directory.
  if HERE!=Path('/data/ford-camera-community-beta-v0.1'):raise RuntimeError('Extract into /data/ford-camera-community-beta-v0.1 exactly.')
  with Path('/data/ford-sidecamera-setup.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    {'check':status,'prepare':prepare,'deploy':deploy,'restore':restore}[args.action]()
if __name__=='__main__':
  try:main()
  except (OSError,ValueError,KeyError,RuntimeError,ImportError,subprocess.CalledProcessError) as e:
    print('STOP:',e,file=sys.stderr);sys.exit(2)
