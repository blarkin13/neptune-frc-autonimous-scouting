"""Detached Windows updater; called only after a verified code-only release is staged."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def wait_for_parent(pid, timeout=90):
    if os.name != 'nt':
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    SYNCHRONIZE = 0x00100000
    handle = kernel.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        if kernel.WaitForSingleObject(handle, timeout * 1000) != 0:
            raise RuntimeError('The helper did not close before the update deadline.')
    finally:
        kernel.CloseHandle(handle)


def apply(app_dir, stage):
    app_dir = Path(app_dir).resolve()
    stage = Path(stage).resolve()
    if stage.parent != app_dir.parent / 'updates' or not stage.name.startswith('stage-'):
        raise ValueError('The update stage is outside the Neptune app directory.')
    expected = json.loads((stage / 'files.json').read_text(encoding='utf-8'))
    if not isinstance(expected, dict) or not expected or any(not re.fullmatch(r'app/(?:(?:robot-detector|field-detector|field-regions)/)?[A-Za-z0-9_.-]+', name) or name in ('app/.', 'app/..', 'app/trainer-connection.json') for name in expected):
        raise ValueError('The update file list is invalid.')
    for name, sha in expected.items():
        if digest(stage / name) != sha:
            raise ValueError('The staged update failed verification.')
    backup = stage / 'rollback'
    backup.mkdir(exist_ok=False)
    replaced = []
    try:
        for name in sorted(expected, key=lambda n: n == 'app/build-version.json'):
            target = app_dir / name[4:]
            previous = backup / name[4:]
            target.parent.mkdir(parents=True, exist_ok=True); previous.parent.mkdir(parents=True, exist_ok=True)   # data folders
            if target.exists():
                shutil.copy2(target, previous)
            temporary = target.with_name(target.name + '.neptune-next')
            shutil.copy2(stage / name, temporary)
            os.replace(temporary, target)
            replaced.append((target, previous))
        for name, sha in expected.items():
            if digest(app_dir / name[4:]) != sha:
                raise ValueError('The installed update failed verification.')
    except Exception:
        for target, previous in reversed(replaced):
            if previous.exists():
                shutil.copy2(previous, target)
            else:
                target.unlink(missing_ok=True)
        raise
    (stage / 'result.json').write_text(json.dumps({'status': 'installed', 'version': json.loads((app_dir / 'build-version.json').read_text())['version']}), encoding='utf-8')


if __name__ == '__main__':
    parent, app, stage = sys.argv[1:]
    try:
        wait_for_parent(int(parent))
        apply(app, stage)
    except Exception as error:
        Path(stage).mkdir(parents=True, exist_ok=True)
        (Path(stage) / 'result.json').write_text(json.dumps({'status': 'failed', 'error': str(error)[:500]}), encoding='utf-8')
        sys.exit(1)
