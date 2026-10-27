#!/usr/bin/env python3
"""Build a generic Debian/Ubuntu desktop package; browser pairing adds credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = '6.6.15'


def ar_member(name, data):
    header = (f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n').encode()
    if len(header) != 60: raise ValueError('Invalid Debian archive header.')
    return header + data + (b'\n' if len(data) % 2 else b'')


def tar_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz', format=tarfile.GNU_FORMAT) as archive:
        # dpkg creates only the folders the archive lists, so list every parent folder before its files.
        folders = sorted({'/'.join(name.split('/')[:i]) for name in files for i in range(1, name.count('/')+1)})
        for folder in folders:
            info = tarfile.TarInfo('./' + folder + '/'); info.type = tarfile.DIRTYPE; info.mode = 0o755
            info.uid = info.gid = 0; info.uname = info.gname = 'root'; info.mtime = 0
            archive.addfile(info)
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo('./' + name)
            info.size = len(data)
            info.mode = mode
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def build(base, output):
    with tempfile.TemporaryDirectory(prefix='neptune-linux-deb-') as temp:
        stage = Path(temp)
        with zipfile.ZipFile(base) as archive:
            names = archive.namelist()
            if any(not name.startswith('neptune-trainer/') or '..' in Path(name).parts for name in names):
                raise ValueError('Unexpected Linux package path.')
            if any(name.endswith('trainer-connection.json') for name in names):
                raise ValueError('The Debian package must contain no private connection.')
            archive.extractall(stage)
        app = stage / 'neptune-trainer/app'
        import sys
        sys.path.insert(0, str(ROOT / 'engine'))
        import neptune_engine
        for name in neptune_engine.FILES:
            shutil.copy2(ROOT / 'engine' / name, app / name)
        for name in ('neptune_trainer_entry.py', 'neptune_trainer_pairing.py'):
            shutil.copy2(ROOT / 'trainer-app/common' / name, app / name)
        shutil.copy2(ROOT / 'trainer-app/linux/Neptune.png', app / 'Neptune.png')
        (app / 'build-version.json').write_text(json.dumps({'version': VERSION}) + '\n')
        # Shipped detectors and region data live in folders next to the engine files.
        for name in ('robot-detector', 'field-detector', 'field-regions'):
            shutil.rmtree(app / name, ignore_errors=True)
            shutil.copytree(ROOT / 'engine' / name, app / name, ignore=shutil.ignore_patterns('README.md'))
        files = {'usr/share/neptune-training-helper/app/' + path.relative_to(app).as_posix(): (path.read_bytes(), 0o644)
                 for path in app.rglob('*') if path.is_file()}
        bootstrap = ROOT / 'trainer-app/linux/bootstrap.py'
        icon = ROOT / 'trainer-app/linux/Neptune.png'
        files['usr/share/neptune-training-helper/bootstrap.py'] = (bootstrap.read_bytes(), 0o644)
        files['usr/share/neptune-training-helper/neptune_ui.py'] = ((ROOT / 'engine/neptune_ui.py').read_bytes(), 0o644)
        files['usr/share/icons/hicolor/256x256/apps/neptune-training-helper.png'] = (icon.read_bytes(), 0o644)
        files['usr/bin/neptune-training-helper'] = (b'#!/bin/sh\nexec /usr/bin/python3 /usr/share/neptune-training-helper/bootstrap.py "$@"\n', 0o755)
        files['usr/share/applications/neptune-training-helper.desktop'] = (
            b'[Desktop Entry]\nType=Application\nName=Neptune Training Helper\nComment=Train and review FRC match video on this computer\nExec=neptune-training-helper\nIcon=neptune-training-helper\nTerminal=false\nCategories=Education;Science;\n', 0o644)
        size = sum(len(data) for data, _ in files.values())
        control = (f'Package: neptune-training-helper\nVersion: {VERSION}\nSection: science\n'
                   'Priority: optional\nArchitecture: all\n'
                   'Maintainer: Neptune FRC <software@neptunefrc.com>\n'
                   'Depends: python3 (>= 3.11), python3-venv, python3-tk, ffmpeg, libgl1, '
                   'libglib2.0-0t64 | libglib2.0-0, ca-certificates, curl\n'
                   f'Installed-Size: {(size + 1023) // 1024}\n'
                   'Description: Neptune Training Helper for robot scouting video\n'
                   ' An owner-paired desktop helper for training and reviewing FRC robot video.\n'
                   ' First launch installs verified Python and YouTube tools for this user.\n').encode()
        archive = b'!<arch>\n'
        archive += ar_member('debian-binary', b'2.0\n')
        archive += ar_member('control.tar.gz', tar_bytes({'control': (control, 0o644)}))
        archive += ar_member('data.tar.gz', tar_bytes(files))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(archive)
        print(output, output.stat().st_size, hashlib.sha256(archive).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('base', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.base, args.output)
