#!/usr/bin/env python3
"""Build a versioned stationary-beta ZIP from an explicit source allowlist."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME='ford-camera-community-beta-v0.1'

def source_files():
 paths=[ROOT/name for name in ('README.md','NOTICE.md','CONTRIBUTING.md','manifest.json','setup.py','build_helpers.py','verify.py','monitor.py','test_installer.py','test_toggle.py')]
 for directory,suffixes in [('files',{'.py','.h','.sh'}),('tests',{'.py','.h','.c'}),('docs',{'.md'}),('tools',{'.py'})]:
  paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in suffixes and '__pycache__' not in p.parts)
 for p in paths:
  if not p.is_file() or p.is_symlink():raise RuntimeError('Missing or symlinked release source: '+str(p))
 return sorted(set(paths))

def build():
 manifest=json.loads((ROOT/'manifest.json').read_text())
 for relative,entry in manifest.items():
  p=ROOT/'files'/relative
  if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['installed']:
   raise RuntimeError('Payload differs from stationary manifest: '+relative)
 paths=source_files()
 checksums={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
 checksum_bytes=(json.dumps(checksums,indent=2)+'\n').encode()
 # Generated integrity manifest covers release inputs, not itself.
 (ROOT/'checksums.json').write_bytes(checksum_bytes)
 destination=ROOT/'dist';destination.mkdir(exist_ok=True)
 archive=destination/(NAME+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in paths:
   info=zipfile.ZipInfo(str(Path(NAME)/p.relative_to(ROOT)),date_time=(2026,10,24,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,p.read_bytes())
  info=zipfile.ZipInfo(NAME+'/checksums.json',date_time=(2026,10,24,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
  z.writestr(info,checksum_bytes)
 sha=hashlib.sha256(archive.read_bytes()).hexdigest()
 (destination/(archive.name+'.sha256')).write_text(sha+'  '+archive.name+'\n')
 print(archive);print('SHA256:',sha)
 return archive
if __name__=='__main__':build()
