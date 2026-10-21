#!/usr/bin/env python3
"""Fetch official build inputs with fixed version and SHA256 checks."""
import hashlib,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'.helper-build/native/deps';ROOT.mkdir(parents=True,exist_ok=True)
INPUTS=[('sparkle.tar.xz','https://github.com/sparkle-project/Sparkle/releases/download/2.10.0/Sparkle-2.10.0.tar.xz','c2bf58aa8387266ac179357b1415d6f2635f044da8be41042af32425dae6da0c','sparkle'),('python.tar.gz','https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.13.16%2B20261013-aarch64-apple-darwin-install_only_stripped.tar.gz','16a5332fb0dcb77f163fc8f8cbccd95be1644cc53e68e5d2a79f50afd6680a0e','runtime')]
# Source-only inputs for the local tools. Hashes match the audited existing distribution.
VENDOR=ROOT.parents[1]/'vendor';VENDOR.mkdir(parents=True,exist_ok=True)
for name,url,sha in [('ffmpeg-9.0.2.tar.xz','https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz','8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'),('quickjs-2026-06-04.tar.xz','https://bellard.org/quickjs/quickjs-2026-06-04.tar.xz','b376e839b322978313d929fd20663b11ba58b75df5a46c126dd19ea2fa70ad2a')]:
    archive=VENDOR/name
    if not archive.exists():subprocess.run(['/usr/bin/curl','--fail','--location','--proto','=https',url,'-o',str(archive)],check=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=sha:raise SystemExit('Checksum mismatch: '+name)
for name,url,sha,dest in INPUTS:
    archive=ROOT/name
    if not archive.exists():subprocess.run(['/usr/bin/curl','--fail','--location','--proto','=https','--tlsv1.2',url,'-o',str(archive)],check=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=sha:raise SystemExit('Checksum mismatch: '+name)
    target=ROOT/dest
    if not target.exists():
        target.mkdir()
        with tarfile.open(archive) as t:t.extractall(target,filter='data')
    print(name,'verified')
