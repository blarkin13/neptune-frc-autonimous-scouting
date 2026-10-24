#!/usr/bin/env python3
"""Build Neptune's signed apt repository from the Linux helper .deb, ready to serve at neptunefrc.com/apt.

    python3 build-apt-repo.py Neptune-Training-Helper_all.deb OUTPUT

Linux PCs add it once (the setup lines are on Auto Scout -> Helpers & settings), then
`sudo apt install neptune-training-helper` installs the helper and `sudo apt upgrade` updates it.
Signs with the key in ~/Documents/ChatGPT/Neptune/apt-signing (never in git).
"""
import argparse
import datetime
import gzip
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

KEY_HOME = Path.home()/'Documents/ChatGPT/Neptune/apt-signing'
ARCHES = ('amd64', 'arm64', 'all')     # the helper is Architecture: all; listed for every host apt asks about


def deb_control(deb):
    """The control file of a .deb (an ar archive holding control.tar.gz)."""
    data = Path(deb).read_bytes()
    assert data[:8] == b'!<arch>\n', 'not a Debian package'
    i = 8
    while i < len(data):
        header = data[i:i+60]; name = header[:16].decode().strip().rstrip('/'); size = int(header[48:58])
        if name == 'control.tar.gz':
            with tarfile.open(fileobj=io.BytesIO(data[i+60:i+60+size])) as t:
                return t.extractfile('./control').read().decode()
        i += 60+size+(size % 2)
    raise ValueError('control.tar.gz missing')


def hashes(blob):
    return {'MD5Sum': hashlib.md5(blob).hexdigest(), 'SHA1': hashlib.sha1(blob).hexdigest(), 'SHA256': hashlib.sha256(blob).hexdigest()}


def build(deb, out):
    out = Path(out); fingerprint = (KEY_HOME/'fingerprint.txt').read_text().strip()
    control = deb_control(deb).strip()
    fields = dict(line.split(': ', 1) for line in control.splitlines() if ': ' in line and not line.startswith(' '))
    pool = out/'pool/main/n'/fields['Package']; pool.mkdir(parents=True, exist_ok=True)
    name = '%s_%s_all.deb' % (fields['Package'], fields['Version'])
    shutil.copy2(deb, pool/name)
    blob = (pool/name).read_bytes(); h = hashes(blob)
    entry = control+'\nFilename: pool/main/n/%s/%s\nSize: %d\nMD5sum: %s\nSHA1: %s\nSHA256: %s\n' % (
        fields['Package'], name, len(blob), h['MD5Sum'], h['SHA1'], h['SHA256'])
    index = {}
    for arch in ARCHES:
        folder = out/'dists/stable/main'/('binary-'+arch); folder.mkdir(parents=True, exist_ok=True)
        (folder/'Packages').write_text(entry+'\n')
        (folder/'Packages.gz').write_bytes(gzip.compress((entry+'\n').encode(), mtime=0))
        for f in ('Packages', 'Packages.gz'):
            index['main/binary-%s/%s' % (arch, f)] = (folder/f).read_bytes()
    release = ['Origin: Neptune FRC', 'Label: Neptune FRC', 'Suite: stable', 'Codename: stable',
               'Date: '+datetime.datetime.now(datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S UTC'),
               'Architectures: '+' '.join(ARCHES), 'Components: main', 'Description: Neptune FRC training helper']
    for algo in ('MD5Sum', 'SHA1', 'SHA256'):
        release.append(algo+':')
        release += [' %s %d %s' % (hashes(b)[algo], len(b), path) for path, b in sorted(index.items())]
    dists = out/'dists/stable'; (dists/'Release').write_text('\n'.join(release)+'\n')
    env = dict(os.environ, GNUPGHOME=str(KEY_HOME/'gnupg'))
    for args, target in ((['--clearsign'], 'InRelease'), (['--detach-sign'], 'Release.gpg')):
        (dists/target).unlink(missing_ok=True)
        subprocess.run(['gpg', '--batch', '--yes', '--local-user', fingerprint, '--digest-algo', 'SHA256', *args,
                        '-o', str(dists/target), str(dists/'Release')], check=True, env=env)
    shutil.copy2(KEY_HOME/'neptune.gpg', out/'neptune.gpg')
    print(out, fields['Package'], fields['Version'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('deb', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.deb, args.output)
