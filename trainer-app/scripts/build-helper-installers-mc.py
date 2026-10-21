#!/usr/bin/env python3
"""Maintenance Console package: Neptune Helper v4 downloads (Mac, Windows, Linux) and setup page.
Run scripts/build-helper-installers.py first. No database changes."""
from pathlib import Path
import hashlib,json,shutil,zipfile
root=Path(__file__).resolve().parents[1]
out=root.parent/'feature-blueprint'
inst=root/'.helper-build/installers'
dl='public_html/Neptune/community/downloads/'
shutil.copy2(inst/'Neptune-Helper-Mac-AppleSilicon-v4.zip',root/(dl+'Neptune-Helper-Pilot.zip'))
shutil.copy2(inst/'Neptune-Helper-Windows-x64-v4.zip',root/(dl+'Neptune-Helper-Windows.zip'))
shutil.copy2(inst/'Neptune-Helper-Linux-v4.zip',root/(dl+'Neptune-Helper-Linux.zip'))
sha=lambda b:hashlib.sha256(b).hexdigest()
# Expected live versions: the last installed package that shipped each file.
bases={'public_html/Neptune/community/index.php':'Neptune_Community_Easy_Tagging_Guide_v8.zip',
       'public_html/Neptune/community/download-helper.php':'Neptune_Helper_Browser_Connect_v1_Maintenance_Console.zip',
       dl+'Neptune-Helper-Pilot.zip':'Neptune_Helper_Observation_Format_v1.zip'}
base={}
for path,package in bases.items():
    src=[p for p in (out/package,root.parent/'maintenance-fixes'/package,root/'maintenance-fixes'/package) if p.is_file()][0]
    base[path]=sha(zipfile.ZipFile(src).read(path))
base[dl+'Neptune-Helper-Windows.zip']=None
base[dl+'Neptune-Helper-Linux.zip']=None
package=out/'Neptune_Helper_Facts_Installers_v4.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for p in base: z.write(root/p,p)
    z.writestr('neptune-package.json',json.dumps({'base':base},indent=2))
assert zipfile.ZipFile(package).testzip() is None
assert package.stat().st_size<50*1024**2,'Maintenance Console upload limit exceeded'
Path(str(package)+'.sha256').write_text(sha(package.read_bytes())+'  '+package.name+'\n')
print(package, round(package.stat().st_size/1024**2,1),'MiB'); print(json.dumps(base,indent=1))
