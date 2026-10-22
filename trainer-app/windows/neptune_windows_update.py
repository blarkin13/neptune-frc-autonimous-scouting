"""Windows helper updates from Neptune's fixed HTTPS release endpoint.

The public update contains code only. The personalized trainer connection and all
job/review data are outside the update archive and are never replaced.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

FEED_URL = 'https://neptunefrc.com/community/downloads/windows/latest.json'
ARCHIVE_PREFIX = 'https://neptunefrc.com/community/downloads/windows/'
MAX_ARCHIVE = 12 * 1024 * 1024
MAX_FEED = 16 * 1024
NAME = re.compile(r'^app/[A-Za-z0-9_.-]+$')
VERSION = re.compile(r'^\d+(?:\.\d+){1,2}$')


class UpdateError(ValueError):
    pass


def _read_https(url, maximum):
    if not url.startswith(ARCHIVE_PREFIX) and url != FEED_URL:
        raise UpdateError('The update URL is not Neptune’s Windows release endpoint.')
    request = urllib.request.Request(url, headers={'User-Agent': 'Neptune-Training-Helper-Windows'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=25) as response:
        if response.geturl() != url:
            raise UpdateError('The update endpoint redirected unexpectedly.')
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise UpdateError('The update is larger than the published limit.')
    return data


def installed_version(app_dir):
    value = json.loads((Path(app_dir) / 'build-version.json').read_text(encoding='utf-8'))['version']
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise UpdateError('The installed Windows version is invalid.')
    return value


def newer(candidate, installed):
    return tuple(int(x) for x in candidate.split('.')) > tuple(int(x) for x in installed.split('.'))


def check(app_dir):
    data = json.loads(_read_https(FEED_URL, MAX_FEED))
    if data.get('schema_version') != 1 or data.get('platform') != 'windows-x64':
        raise UpdateError('The Windows release feed has an unexpected format.')
    version = data.get('version')
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise UpdateError('The Windows release version is invalid.')
    if data.get('archive_url') != ARCHIVE_PREFIX + 'Neptune-Training-Helper-' + version + '-update.zip':
        raise UpdateError('The Windows release archive URL is invalid.')
    if not isinstance(data.get('archive_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', data['archive_sha256']):
        raise UpdateError('The Windows release checksum is invalid.')
    size = data.get('archive_size')
    if not isinstance(size, int) or not 0 < size <= MAX_ARCHIVE:
        raise UpdateError('The Windows release size is invalid.')
    return data if newer(version, installed_version(app_dir)) else None


def prepare(app_dir, release, update_root=None):
    app_dir = Path(app_dir)
    if release['version'] == installed_version(app_dir) or not newer(release['version'], installed_version(app_dir)):
        raise UpdateError('This release is not newer than the installed app.')
    if update_root is None:
        update_root = app_dir.parent / 'updates'
    update_root = Path(update_root)
    update_root.mkdir(parents=True, exist_ok=True)
    payload = _read_https(release['archive_url'], MAX_ARCHIVE)
    if len(payload) != release['archive_size'] or hashlib.sha256(payload).hexdigest() != release['archive_sha256']:
        raise UpdateError('The Windows update failed its size or SHA-256 check.')
    archive = update_root / ('Neptune-Training-Helper-' + release['version'] + '-update.zip')
    pending = archive.with_suffix('.partial')
    pending.write_bytes(payload)
    pending.replace(archive)
    stage = update_root / ('stage-' + release['version'])
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        with zipfile.ZipFile(archive) as z:
            entries = z.namelist()
            if len(entries) != len(set(entries)) or 'files.json' not in entries:
                raise UpdateError('The Windows update has duplicate or missing files.')
            if any(not NAME.fullmatch(name) and name != 'files.json' for name in entries):
                raise UpdateError('The Windows update contains an unexpected path.')
            expected = json.loads(z.read('files.json'))
            if not isinstance(expected, dict) or set(expected) != set(entries) - {'files.json'}:
                raise UpdateError('The Windows update file list is invalid.')
            if 'app/trainer-connection.json' in expected or 'app/build-version.json' not in expected:
                raise UpdateError('The Windows update attempted to replace a connection.')
            for name, sha in expected.items():
                if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
                    raise UpdateError('The Windows update has an invalid file hash.')
                info = z.getinfo(name)
                if info.file_size > 5 * 1024 * 1024:
                    raise UpdateError('An update file is unexpectedly large.')
                data = z.read(info)
                if hashlib.sha256(data).hexdigest() != sha:
                    raise UpdateError('A Windows update file failed its checksum.')
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            if installed_version(stage / 'app') != release['version']:
                raise UpdateError('The downloaded Windows app version differs from the feed.')
            (stage / 'files.json').write_text(json.dumps(expected, sort_keys=True), encoding='utf-8')
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def launch_apply(app_dir, stage):
    if sys.platform != 'win32':
        raise UpdateError('Automatic installation runs only on Windows.')
    app_dir = Path(app_dir)
    stage = Path(stage)
    script = app_dir / 'neptune_update_apply.py'
    if not script.is_file():
        raise UpdateError('The Windows update installer is missing.')
    detached = stage / 'apply-update.py'
    shutil.copy2(script, detached)
    python = Path(sys.executable).with_name('python.exe')
    subprocess.Popen([str(python), '-I', str(detached), str(os.getpid()), str(app_dir), str(stage)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
