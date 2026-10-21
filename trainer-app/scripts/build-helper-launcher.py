#!/usr/bin/env python3
"""Build the Mac double-click launcher and its Maintenance Console update."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--download-only',action='store_true')
parser.add_argument('--version',default='3')
parser.add_argument('--patch-name',default='Neptune_Helper_Runtime_Reuse_v1.zip')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
old_download_hash=hashlib.sha256((root/'public_html/Neptune/community/downloads/Neptune-Helper-Pilot.zip').read_bytes()).hexdigest()
output=root.parent/'feature-blueprint'
stage=root/'.helper-build/distribution/Neptune Helper'
stage.mkdir(parents=True,exist_ok=True)
for name in ['Start Neptune Helper.command','requirements.json','requirements.txt','neptune_app.py','neptune_setup.py','neptune_helper.py','neptune_helper_gui.py','neptune_connect.py']:
    shutil.copy2(root/'helper'/name,stage/name)
shutil.copytree(root/'.helper-build/bundle/vendor',stage/'vendor',dirs_exist_ok=True)
shutil.copytree(root/'.helper-build/wheels',stage/'wheels',dirs_exist_ok=True)
licenses=stage/'licenses';licenses.mkdir(exist_ok=True)
shutil.copy2('/opt/homebrew/Cellar/ollama/0.40.6/LICENSE',licenses/'OLLAMA-LICENSE.txt')
shutil.copy2(root/'.helper-build/vendor/ffmpeg-9.0.2/COPYING.LGPLv2.1',licenses/'FFMPEG-LICENSE.txt')
shutil.copy2(root/'.helper-build/vendor/quickjs-2026-06-04/LICENSE',licenses/'QUICKJS-LICENSE.txt')
sources=stage/'sources';sources.mkdir(exist_ok=True)
shutil.copy2(root/'.helper-build/vendor/ffmpeg-9.0.2.tar.xz',sources/'ffmpeg-9.0.2.tar.xz')
shutil.copy2(root/'.helper-build/vendor/quickjs-2026-06-04.tar.xz',sources/'quickjs-2026-06-04.tar.xz')
(sources/'build-quickjs.sh').write_text('tar -xf quickjs-2026-06-04.tar.xz\ncd quickjs-2026-06-04\nMACOSX_DEPLOYMENT_TARGET=14.0 make -j4 qjs\n')
(sources/'build-ffmpeg.sh').write_text('''#!/bin/sh
set -eu
tar -xf ffmpeg-9.0.2.tar.xz
cd ffmpeg-9.0.2
./configure --prefix=/tmp/neptune-ffmpeg-unused --disable-everything --disable-autodetect --disable-network --disable-shared --enable-static --disable-doc --disable-debug --extra-cflags=-mmacosx-version-min=14.0 --extra-ldflags=-mmacosx-version-min=14.0 --enable-ffmpeg --enable-ffprobe --enable-protocol=file --enable-demuxer=mov,matroska,avi,flv,mpegts --enable-decoder=h264,hevc,vp9,vp8,av1,mjpeg,png --enable-parser=h264,hevc,vp9,vp8,av1 --enable-encoder=mjpeg --enable-muxer=image2 --enable-filter=scale --enable-swscale
make -j4
''')
(stage/'START HERE.txt').write_text('''NEPTUNE HELPER — APPLE SILICON MAC PILOT

1. Unzip this download and keep the entire Neptune Helper folder together.
2. Double-click Start Neptune Helper.command.
3. Setup checks requirements, installs missing Python through its official macOS installer when necessary, creates a private environment and opens the helper. No commands need to be typed.
4. The helper checks its included video/AI tools and downloads the local model if missing (about 3.2 GB). Existing copies of the approved model are reused. Existing working Homebrew video tools and Ollama are also reused. YouTube support prefers an existing Deno or Node runtime before the bundled QuickJS executable; downloaded executables still require macOS approval.
5. Click Connect to Neptune and approve the matching request in your browser. No token needs to be copied. Choose a season (2026 onward), choose an event, select an available match and click Go. The helper downloads its linked individual YouTube video automatically. Matches without video stay visible as video_needed. YouTube may restrict or temporarily block individual downloads; no browser cookies or paid fallback are used.
6. An animation and status updates show work. When results are ready, review the summary and timestamped observations, optionally open the video, then click Submit results. Nothing submits automatically.

Requires Apple Silicon (M-series), macOS 14+, an internet connection for initial setup and Neptune, and 5 GB free space if the model is missing. Intel Mac, Windows and Linux launchers are not included in this build.
The launcher opens Terminal as a progress window, like AUTOMATIC1111's setup scripts. Keep it open while using the helper. You do not need Homebrew, Git, a paid API, or a separately installed Ollama app.
If Python is missing, macOS may ask for your password in the official Python installer. Canceling leaves setup incomplete; double-click the launcher to retry. No security settings are changed by this script. The launcher is not notarized and may require macOS's normal downloaded-software approval.

Use the same launcher next time. It checks and reuses requirements rather than installing them again. Python itself stays installed; private Python packages are stored in ~/Library/Application Support/Neptune Helper. The model uses ~/.ollama/models so existing Ollama model files can be reused. The helper's private engine disables cloud features and stops when the helper closes. It does not change any existing Ollama service or configuration.

Results are AI drafts and may contain factual errors. A different Neptune reviewer still approves public publication. Keep the helper open while reviewing so your reservation can be renewed. Connection credentials stay behind the scenes while the helper is open. This pilot has not been validated as accurate robot tracking or scoring attribution.

This package includes a machine-readable requirements.json, hash-pinned Python-package requirements.txt and a file integrity manifest. FFmpeg's corresponding source and build configuration are in sources/. Ollama/runtime licenses and the certificate wheel's license are included. Model license/source: https://ollama.com/library/qwen2.5vl:3b . Python installer source: https://www.python.org/downloads/release/python-31316/ .
''')
hashes={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='files.json'}
(stage/'files.json').write_text(json.dumps(hashes,indent=2)+'\n')
archive=output/('Neptune-Helper-Mac-Setup-v'+args.version+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(stage.rglob('*')):
        if p.is_file():z.write(p,str(Path('Neptune Helper')/p.relative_to(stage)))
# Keep the existing authenticated download endpoint; replace its fixed payload.
serverzip=root/'public_html/Neptune/community/downloads/Neptune-Helper-Pilot.zip'
serverzip.write_bytes(archive.read_bytes())
p=root/'public_html/Neptune/community/index.php'
# Exact installed versions were those shipped in the earlier download-fix and original pilot packages.
previousfix=zipfile.ZipFile(root.parent/'maintenance-fixes/Neptune_Community_Helper_Download_Fix_v1.zip')
previouspilot=zipfile.ZipFile(output/'Neptune_Community_Analysis_Pilot_v1_Maintenance_Console.zip')
index='public_html/Neptune/community/index.php';download='public_html/Neptune/community/downloads/Neptune-Helper-Pilot.zip'
endpoint='public_html/Neptune/community/download-helper.php'
# The setup instructions replace either previously delivered version of this feature page.
# Its contents are new, so the console's stale-version check remains active.
if args.download_only:
    patch=output/args.patch_name
    with zipfile.ZipFile(patch,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(serverzip,download)
        z.writestr('neptune-package.json',json.dumps({'base':{download:old_download_hash}},indent=2))
else:
    previousconnect=zipfile.ZipFile(output/'Neptune_Helper_Browser_Connect_v1_Maintenance_Console.zip')
    files=['neptune_secure/community-catalog.php','neptune_secure/community-analysis.php','public_html/Neptune/api/community-analysis.php','public_html/Neptune/community/index.php','public_html/Neptune/admin/community-analysis.php',download]
    base={}
    for name in files:
        if name=='neptune_secure/community-catalog.php':base[name]=None
        elif name in previousconnect.namelist():base[name]=hashlib.sha256(previousconnect.read(name)).hexdigest()
        elif name in previouspilot.namelist():base[name]=hashlib.sha256(previouspilot.read(name)).hexdigest()
    patch=output/'Neptune_Community_Catalog_v1.zip'
    with zipfile.ZipFile(patch,'w',zipfile.ZIP_DEFLATED) as z:
        for name in files:z.write(root/name,name)
        z.writestr('neptune-package.json',json.dumps({'base':base},indent=2))
for p in [archive,patch]:
    assert zipfile.ZipFile(p).testzip() is None
    Path(str(p)+'.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
print('Launcher:',archive,round(archive.stat().st_size/1024**2,1),'MiB')
print('Maintenance patch:',patch,round(patch.stat().st_size/1024**2,1),'MiB')
assert patch.stat().st_size<50*1024**2,'Maintenance Console upload limit exceeded'
