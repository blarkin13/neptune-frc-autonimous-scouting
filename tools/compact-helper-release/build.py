import copy,hashlib,importlib.util,io,json,plistlib,re,tarfile,zipfile
from pathlib import Path
from raw_zip_merge import merge
ROOT=Path(__file__).resolve().parents[2]
OUT=Path('/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/compact-helper-release');OUT.mkdir(exist_ok=True,parents=True)
ENGINE='2.7.27-live-dashboard'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patched_engine(raw):
    s,n=re.subn(r"(?m)^VERSION = '[^']+'$",f"VERSION = '{ENGINE}'",raw.decode());assert n==1;return s.encode()
def replacements(base,prefix,version):
    d={prefix+n:(ROOT/'engine'/n).read_bytes() for n in ('neptune_trainer.py','neptune_ui.py','neptune_robot_jobs.py','neptune_telemetry.py')}
    d[prefix+'neptune_engine.py']=patched_engine(base[prefix+'neptune_engine.py'])
    d[prefix+'build-version.json']=(json.dumps({'version':version})+'\n').encode();return d
# Windows: retain every other reviewed code/runtime entry from 6.5.13.
win=OUT/'windows';win.mkdir(exist_ok=True)
base=Path('/Users/brianlarkin/Documents/ChatGPT/autonomous_scouting/local/windows-detector-fix-6.5.13/Neptune-Training-Helper-6.5.13-update.zip')
with zipfile.ZipFile(base) as z:d={n:z.read(n) for n in z.namelist() if n!='files.json'}
d.update(replacements(d,'app/','6.5.15'))
with zipfile.ZipFile(win/'Neptune-Training-Helper-6.5.15-update.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for n,b in sorted(d.items()):
        if n.endswith('.py'):compile(b,n,'exec')
        z.writestr(n,b)
    z.writestr('files.json',json.dumps({n:hashlib.sha256(b).hexdigest() for n,b in d.items()},sort_keys=True))
a=win/'Neptune-Training-Helper-6.5.15-update.zip';feed={'schema_version':1,'platform':'windows-x64','version':'6.5.15','engine_version':ENGINE,'archive_url':'https://neptunefrc.com/community/downloads/windows/'+a.name,'archive_sha256':sha(a),'archive_size':a.stat().st_size};(win/'latest.json').write_text(json.dumps(feed,indent=2)+'\n')
# Linux: preserve package files, permissions and dependencies; replace shared UI/engine code.
base=Path('/Users/brianlarkin/Documents/ChatGPT/Neptune/Linux-Helper-6.6.5-ready/Neptune-Training-Helper_all.deb');raw=base.read_bytes();assert raw[:8]==b'!<arch>\n';i=8;members={}
while i<len(raw):
    h=raw[i:i+60];size=int(h[48:58]);members[h[:16].decode().strip().rstrip('/')]=raw[i+60:i+60+size];i+=60+size+(size%2)
with tarfile.open(fileobj=io.BytesIO(members['data.tar.gz'])) as t:
    infos=t.getmembers();files={m.name:t.extractfile(m).read() for m in infos if m.isfile()}
prefix='./usr/share/neptune-training-helper/app/';assert prefix+'neptune_ui.py' in files
files.update(replacements(files,prefix,'6.6.7'))
def pack(infos,files):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz',format=tarfile.GNU_FORMAT) as t:
        for old in infos:
            m=copy.copy(old)
            if m.isfile():m.size=len(files[m.name]);t.addfile(m,io.BytesIO(files[m.name]))
            else:t.addfile(m)
    return out.getvalue()
with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz'])) as t:
    ci=t.getmembers();cf={m.name:t.extractfile(m).read() for m in ci if m.isfile()}
for n in cf:
    if n.endswith('control'):cf[n]=cf[n].replace(b'Version: 6.6.5',b'Version: 6.6.7')
def ar(name,b):return (f'{name+"/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(b):<10}`\n').encode()+b+(b'\n' if len(b)%2 else b'')
# gzip timestamps fixed explicitly, so the server can rebuild the identical package.
import gzip
members['data.tar.gz']=gzip.compress(gzip.decompress(pack(infos,files)),mtime=0)
members['control.tar.gz']=gzip.compress(gzip.decompress(pack(ci,cf)),mtime=0)
linux=OUT/'linux';linux.mkdir(exist_ok=True);deb=linux/'Neptune-Training-Helper_all.deb';deb.write_bytes(b'!<arch>\n'+b''.join(ar(n,members[n]) for n in ('debian-binary','control.tar.gz','data.tar.gz')))
# A small rebuilding kit carries the already-compressed changed tar plus original model bytes.
# Full package is modest enough to publish normally alongside apt indexes.
(linux/'base-sha256.txt').write_text(sha(base)+'\n')
# Mac: patch only reviewed app/code/signature entries in the prior full signed release.
mac=OUT/'mac';mac.mkdir(exist_ok=True)
base=Path('/Users/brianlarkin/Documents/ChatGPT/Neptune/Mac-Helper-3.2.37-ready/public-release/Neptune-Training-Helper-3.2.37.zip');app=Path('/private/tmp/neptune-compact-3.2.42/Neptune Training Helper.app')
paths=['Contents/MacOS/NeptuneTrainingHelper','Contents/Info.plist','Contents/_CodeSignature/CodeResources','Contents/Resources/engine-identity.json']+['Contents/Resources/engine/'+n for n in ('neptune_trainer.py','neptune_ui.py','neptune_robot_jobs.py','neptune_telemetry.py','neptune_engine.py','native_worker.py')]
patch=OUT/'mac-code-patch.zip'
with zipfile.ZipFile(base) as a,zipfile.ZipFile(patch,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for rel in paths:
        name='Neptune Training Helper.app/'+rel;z.writestr(copy.copy(a.getinfo(name)),(app/rel).read_bytes())
a=mac/'Neptune-Training-Helper-3.2.42.zip';merge(base,patch,a)
(OUT/'packages.json').write_text(json.dumps({'windows':{'version':'6.5.15','sha256':sha(win/'Neptune-Training-Helper-6.5.15-update.zip')},'linux':{'version':'6.6.7','sha256':sha(deb)},'mac':{'version':'3.2.42','sha256':sha(a),'base_sha256':sha(base),'patch_sha256':sha(patch)}},indent=2))
print((OUT/'packages.json').read_text())
