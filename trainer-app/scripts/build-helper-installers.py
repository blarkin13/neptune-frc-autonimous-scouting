#!/usr/bin/env python3
"""Build the Neptune Helper installer packages for macOS (Apple Silicon), Windows (x64) and Linux.

Outputs .helper-build/installers/Neptune-Helper-{Mac,Windows,Linux}-v<version>.zip plus .sha256 files.
Nothing is uploaded or published. The Mac package reuses the existing bundled vendor tools; run with
--ffmpeg to use a rebuilt FFmpeg (the facts pipeline needs the fps, crop, split and format filters and
the PPM encoder, which the earlier minimal build did not include).
"""
import argparse
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'helper'
BUILD = ROOT / '.helper-build'
APP_FILES = ['neptune_cache.py','neptune_action_labels.py','neptune_page_worker.py','neptune_scoring_model.py','neptune_engine.py','neptune_clock.py','neptune_events.py','neptune_tracking.py','neptune_yolo.py','neptune_temporal.py','neptune_videomae.py','requirements-videomae.txt','neptune_detector_training.py','requirements-yolo.txt','neptune_app.py', 'neptune_setup.py', 'neptune_helper.py', 'neptune_helper_gui.py', 'neptune_connect.py',
             'neptune_games.py','neptune_training.py','neptune_training_gui.py','neptune_shared_models.py','neptune_facts.py', 'neptune_ocr.py', 'neptune_learning.py', 'neptune_video_labels.py', 'season_rules.json', 'requirements.json','TRAINING.md']

COMMON_NOTES = '''What it does: Neptune Helper downloads one published match video, reads the broadcast scoreboard,
match clock, results screen and robot bumper numbers with on-device text recognition, and drafts a summary
from those facts. Nothing is submitted until you review the draft and click Submit results. No AI model,
paid service or cloud processing is used. Facts it cannot read are reported as unknown; bumper readings it
cannot confirm stay "candidate" and are never presented as identified robots.

Evidence: every run keeps its original readings, frames and crops, the draft and the software versions in
~/.neptune-helper/match-<id>/facts-runs/<time>/ (read-only originals). Reviewer corrections are stored
separately in corrections.jsonl. Training and releases are managed on Neptune's server. The helper checks the shared game model when starting a match. Use Shared models to view its status; no local training is required.
'''


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fresh(path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def zip_folder(stage, archive, top):
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo.from_file(p, str(Path(top) / p.relative_to(stage)))
                info.compress_type = zipfile.ZIP_DEFLATED
                if p.stat().st_mode & stat.S_IXUSR:
                    info.external_attr = 0o100755 << 16
                z.writestr(info, p.read_bytes())
    assert zipfile.ZipFile(archive).testzip() is None
    Path(str(archive) + '.sha256').write_text(sha(archive) + '  ' + archive.name + '\n')
    print('%-48s %6.1f MiB' % (archive.name, archive.stat().st_size / 1024 ** 2))


def mac(version, out, ffmpeg):
    stage = fresh(BUILD / 'installers-stage' / 'mac' / 'Neptune Helper')
    for name in APP_FILES + ['Start Neptune Helper.command', 'requirements.txt']:
        shutil.copy2(HELPER / name, stage / name)
    (stage/'build-version.json').write_text(json.dumps({'version':version})+'\n')
    (stage / 'bin').mkdir()
    shutil.copy2(HELPER / 'bin' / 'neptune-ocr', stage / 'bin' / 'neptune-ocr')
    shutil.copytree(HELPER / 'vision', stage / 'sources' / 'apple-vision-reader')
    shutil.copytree(BUILD / 'bundle' / 'vendor', stage / 'vendor', dirs_exist_ok=True)
    if ffmpeg:
        for tool in ('ffmpeg', 'ffprobe'):
            shutil.copy2(Path(ffmpeg) / tool, stage / 'vendor' / 'bin' / tool)
    shutil.copytree(BUILD / 'wheels', stage / 'wheels', dirs_exist_ok=True)
    licenses = stage / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(BUILD / 'vendor/ffmpeg-9.0.2/COPYING.LGPLv2.1', licenses / 'FFMPEG-LICENSE.txt')
    shutil.copy2(BUILD / 'vendor/quickjs-2026-06-04/LICENSE', licenses / 'QUICKJS-LICENSE.txt')
    sources = stage / 'sources'
    shutil.copy2(BUILD / 'vendor/ffmpeg-9.0.2.tar.xz', sources / 'ffmpeg-9.0.2.tar.xz')
    shutil.copy2(BUILD / 'vendor/quickjs-2026-06-04.tar.xz', sources / 'quickjs-2026-06-04.tar.xz')
    (sources / 'build-ffmpeg.sh').write_text(FFMPEG_BUILD)
    (stage / 'START HERE.txt').write_text('''NEPTUNE HELPER — MAC (APPLE SILICON)

1. Unzip and keep the whole Neptune Helper folder together.
2. Double-click Start Neptune Helper.command. It checks this Mac, installs Python from python.org only if it
   is missing, creates a private environment, checks the included video tools and the Apple Vision text
   reader, and opens the helper.
3. Click Check this computer, then Connect to Neptune and approve the request in your browser.
4. Choose a season, an event and an available match, then click Go. Review the draft, then Submit results.

Requires an Apple Silicon (M-series) Mac with macOS 14 or newer. Intel Macs are not supported.
The launcher and its tools are not notarized; macOS may ask you to approve them once.

''' + COMMON_NOTES)
    hashes = {str(p.relative_to(stage)): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage / 'files.json').write_text(json.dumps(hashes, indent=2) + '\n')
    zip_folder(stage, out / ('Neptune-Helper-Mac-AppleSilicon-v%s.zip' % version), 'Neptune Helper')


def app_folder(stage):
    app = stage / 'app'
    app.mkdir()
    for name in APP_FILES + ['requirements-ocr.txt']:
        shutil.copy2(HELPER / name, app / name)
    return app


def windows(version, out):
    stage = fresh(BUILD / 'installers-stage' / 'windows' / 'Neptune Helper')
    for name in ('Install Neptune Helper.cmd', 'install-neptune-helper.ps1'):
        shutil.copy2(HELPER / 'windows' / name, stage / name)
    app_folder(stage)
    (stage/'app/build-version.json').write_text(json.dumps({'version':version})+'\n')
    (stage / 'START HERE.txt').write_text('''NEPTUNE HELPER — WINDOWS 10/11 (64-bit x86)

1. Unzip the whole folder (do not run it from inside the zip).
2. Double-click "Install Neptune Helper.cmd". No administrator rights are needed. It checks this computer
   and installs only what is missing, each download checked against a pinned SHA-256:
     - Python 3.13.16 from python.org (per user) if no Python 3.11+ with Tk is installed
     - FFmpeg 9.0.2 (gyan.dev essentials build) if FFmpeg is not installed
     - Deno 2.9.7 (YouTube support for yt-dlp) if neither Deno nor Node.js is installed
     - RapidOCR 3.10.0 with ONNX Runtime 1.31.0 and yt-dlp, from hash-locked wheels
   It then runs a self-check and adds "Neptune Helper" to the Start menu and Desktop.
3. Open Neptune Helper, click Check this computer, then Connect to Neptune.

Windows on ARM is not supported. To remove: run install-neptune-helper.ps1 -Uninstall
(saved match work in %USERPROFILE%\\.neptune-helper is kept).

''' + COMMON_NOTES.replace('~/.neptune-helper', '%USERPROFILE%\\.neptune-helper'))
    hashes = {str(p.relative_to(stage)).replace('\\', '/'): sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage / 'files.json').write_text(json.dumps(hashes, indent=2) + '\n')
    zip_folder(stage, out / ('Neptune-Helper-Windows-x64-v%s.zip' % version), 'Neptune Helper')


def linux(version, out):
    stage = fresh(BUILD / 'installers-stage' / 'linux' / 'neptune-helper')
    shutil.copy2(HELPER / 'linux' / 'install-neptune-helper.sh', stage / 'install-neptune-helper.sh')
    (stage / 'install-neptune-helper.sh').chmod(0o755)
    app_folder(stage)
    (stage/'app/build-version.json').write_text(json.dumps({'version':version})+'\n')
    (stage / 'START-HERE.txt').write_text('''NEPTUNE HELPER — LINUX

Supported: Ubuntu 24.04 LTS and Debian 12, on x86_64 or aarch64 (arm64), with a desktop session.
Not supported: Fedora/RHEL, Ubuntu 22.04, 32-bit systems.

1. Unpack the folder, open a terminal in it and run:  ./install-neptune-helper.sh
   It checks this computer and installs only what is missing:
     - apt packages (asks for your password via sudo): python3, python3-venv, python3-tk, ffmpeg,
       libgl1, libglib2.0-0, ca-certificates, curl
     - Deno 2.9.7 (YouTube support for yt-dlp), SHA-256 checked, unless Deno or Node.js is installed
     - RapidOCR 3.10.0 with ONNX Runtime 1.31.0 and yt-dlp, from hash-locked wheels
   Then it runs a self-check, creates ~/.local/bin/neptune-helper and an applications-menu entry.
2. Open Neptune Helper from the applications menu, click Check this computer, then Connect to Neptune.

To remove: ./install-neptune-helper.sh --uninstall (saved match work in ~/.neptune-helper is kept).

''' + COMMON_NOTES)
    lines = ['%s  %s' % (sha(p), p.relative_to(stage)) for p in sorted(stage.rglob('*')) if p.is_file()]
    (stage / 'files.sha256').write_text('\n'.join(lines) + '\n')
    zip_folder(stage, out / ('Neptune-Helper-Linux-v%s.zip' % version), 'neptune-helper')


FFMPEG_BUILD = '''#!/bin/sh
# Minimal static FFmpeg for Neptune Helper (macOS arm64): decoders for match videos, the image filters the
# facts pipeline uses (fps, crop, split, scale, format) and JPEG/PPM image output.
set -eu
tar -xf ffmpeg-9.0.2.tar.xz
cd ffmpeg-9.0.2
./configure --prefix=/tmp/neptune-ffmpeg-unused --disable-everything --disable-autodetect --disable-network \\
  --disable-shared --enable-static --disable-doc --disable-debug \\
  --extra-cflags=-mmacosx-version-min=14.0 --extra-ldflags=-mmacosx-version-min=14.0 \\
  --enable-ffmpeg --enable-ffprobe --enable-protocol=file --enable-demuxer=mov,matroska,avi,flv,mpegts \\
  --enable-decoder=h264,hevc,vp9,vp8,av1,mjpeg,png --enable-parser=h264,hevc,vp9,vp8,av1 \\
  --enable-encoder=mjpeg,ppm --enable-muxer=image2,framemd5 \\
  --enable-filter=scale,fps,crop,split,format,null,aresample,anull --enable-swscale
make -j4
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version', default='4')
    ap.add_argument('--ffmpeg', help='folder holding rebuilt ffmpeg and ffprobe for the Mac package')
    ap.add_argument('--only', choices=['mac', 'windows', 'linux'])
    a = ap.parse_args()
    out = BUILD / 'installers'
    out.mkdir(parents=True, exist_ok=True)
    if a.only in (None, 'mac'):
        mac(a.version, out, a.ffmpeg)
    if a.only in (None, 'windows'):
        windows(a.version, out)
    if a.only in (None, 'linux'):
        linux(a.version, out)


if __name__ == '__main__':
    main()
