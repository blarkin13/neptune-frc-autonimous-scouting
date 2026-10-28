#!/usr/bin/env python3
"""Build Windows installer and code-only updater from the prior public ZIP.

The source ZIP is a release template, never a personalized download. It must not
contain trainer-connection.json. No source archive or credentials are committed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engine'
WINDOWS = ROOT / 'trainer-app/windows'
VERSION = '6.5.47'
URL = 'https://neptunefrc.com/community/downloads/windows/'
RETIRED = ('neptune-art-poseidon.jpg', 'neptune-art-seahorse.jpg', 'neptune-art-circuit.jpg')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_zip(source, target):
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None


def build(base, output):
    sys.path.insert(0, str(ENGINE))
    import neptune_engine
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='neptune-win-release-') as temp:
        stage = Path(temp)
        with zipfile.ZipFile(base) as archive:
            members = archive.namelist()
            if any('..' in Path(name).parts or not name.startswith('Neptune Trainer/') for name in members):
                raise ValueError('Unexpected path in the prior public Windows package.')
            if any(name.endswith('trainer-connection.json') for name in members):
                raise ValueError('Refusing a personalized Windows package.')
            archive.extractall(stage)
        folder = stage / 'Neptune Trainer'
        app = folder / 'app'
        if not (app / 'neptune_engine.py').is_file():
            raise ValueError('The prior Windows package is missing its engine.')
        for name in neptune_engine.FILES:
            shutil.copy2(ENGINE / name, app / name)
        # Files the prior package had that this release no longer ships.
        for name in RETIRED:
            (app / name).unlink(missing_ok=True)
        # Shipped detectors and region data live in folders next to the engine files.
        for name in ('robot-detector', 'field-detector', 'field-regions'):
            shutil.rmtree(app / name, ignore_errors=True)
            shutil.copytree(ENGINE / name, app / name, ignore=shutil.ignore_patterns('README.md'))
        shutil.copy2(ENGINE / 'neptune_trainer.py', app / 'neptune_trainer.py')
        for name in ('neptune_windows_update.py', 'neptune_update_apply.py', 'Neptune.ico'):
            shutil.copy2(WINDOWS / name, app / name)
        for name in ('neptune_trainer_entry.py', 'neptune_trainer_pairing.py'):
            shutil.copy2(ROOT / 'trainer-app/common' / name, app / name)
        shutil.copy2(ROOT / 'trainer-app/linux/Neptune.png', app / 'Neptune.png')
        shutil.copy2(WINDOWS / 'install-neptune-trainer.ps1', folder / 'install-neptune-trainer.ps1')
        (app / 'build-version.json').write_text(json.dumps({'version': VERSION}) + '\n')
        (folder / 'START HERE.txt').write_text(
            'NEPTUNE TRAINING HELPER — WINDOWS 10/11 x64\n\n'
            'For the simplest setup, download Neptune-Training-Helper-Setup.exe instead of this ZIP.\n'
            'If using this ZIP: extract it, then double-click Install Neptune Trainer.cmd.\n'
            'Open Neptune Trainer from the Desktop or Start menu. Connect it in your browser,\n'
            'then leave it open and select this computer on Neptune’s Training & Models page.\n\n'
            'Version ' + VERSION + ' includes engine ' + neptune_engine.VERSION + '. It checks for updates when opened; '
            'use Check for updates in its window to check again and install a newer release. '
            'From 6.5.35 it also installs updates requested from Neptune’s Computers page (or automatically, if turned on there) and reopens itself. '
            'A running match finishes before the app installs an update. The connection, labels, and saved '
            'local match work remain in place. Version 6.2 and older need this one fresh ZIP install '
            'to gain the updater. Windows on ARM is not supported.\n'
        )
        files = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'files.json'}
        (folder / 'files.json').write_text(json.dumps(files, indent=2, sort_keys=True) + '\n')
        full = output / 'Neptune-Trainer-Windows.zip'
        write_zip(stage, full)
        update_root = stage / 'update'
        update_root.mkdir()
        # Updates carry code and small data only: the shipped detector models come with the full installer, and
        # detectors trained on Neptune reach helpers by sync. (Updaters before 6.5.3 refuse files over 5 MB.)
        shutil.copytree(app, update_root / 'app', ignore=shutil.ignore_patterns('trainer-connection.json', '*.pt'))
        update_files = {p.relative_to(update_root).as_posix(): sha(p) for p in sorted((update_root / 'app').rglob('*')) if p.is_file()}
        (update_root / 'files.json').write_text(json.dumps(update_files, indent=2, sort_keys=True) + '\n')
        update = output / ('Neptune-Training-Helper-' + VERSION + '-update.zip')
        write_zip(update_root, update)
        feed = {'schema_version': 1, 'platform': 'windows-x64', 'version': VERSION,
                'engine_version': neptune_engine.VERSION,
                'archive_url': URL + update.name,
                'archive_sha256': sha(update), 'archive_size': update.stat().st_size}
        (output / 'latest.json').write_text(json.dumps(feed, indent=2, sort_keys=True) + '\n')
        (output / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in (full, update, output / 'latest.json')))
        print(json.dumps({'full_bytes': full.stat().st_size, 'update_bytes': update.stat().st_size, 'engine': neptune_engine.VERSION, 'sha256': {p.name: sha(p) for p in (full, update, output / 'latest.json')}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.output)
