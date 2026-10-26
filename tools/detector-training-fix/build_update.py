"""Build a narrowly scoped Windows update from the verified public code archive.

Only detector-job code, its engine version, and the app version are changed.
No unrelated working-tree engine changes or connection files enter this package.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def build(base, base_feed, output):
    raw = Path(base).read_bytes(); prior = json.loads(Path(base_feed).read_text())
    if sha(raw) != prior['archive_sha256'] or len(raw) != prior['archive_size']:
        raise ValueError('Base update does not match the published checksum and size.')
    version = '6.5.13'; engine_version = '2.7.25-bumper-warm-start'
    with zipfile.ZipFile(base) as z:
        expected = json.loads(z.read('files.json'))
        if set(z.namelist()) != set(expected)|{'files.json'}:
            raise ValueError('Unexpected base archive members.')
        files = {name: z.read(name) for name in expected}
        for name, data in files.items():
            if not name.startswith('app/') or '..' in Path(name).parts or 'trainer-connection' in name or sha(data) != expected[name]:
                raise ValueError('Unsafe or unverifiable base file.')
    if json.loads(files['app/build-version.json'])['version'] != '6.5.12':
        raise ValueError('Expected the reviewed Windows 6.5.12 base.')
    files['app/neptune_robot_jobs.py'] = (ROOT/'engine/neptune_robot_jobs.py').read_bytes()
    old_engine = files['app/neptune_engine.py'].decode()
    new_engine, replacements = re.subn(r"(?m)^VERSION = '[^']+'$", f"VERSION = '{engine_version}'", old_engine)
    if replacements != 1:
        raise ValueError('Could not update the engine identity.')
    files['app/neptune_engine.py'] = new_engine.encode()
    files['app/build-version.json'] = (json.dumps({'version': version})+'\n').encode()
    for name, data in files.items():
        if name.endswith('.py'):
            compile(data, name, 'exec')
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    archive = output/f'Neptune-Training-Helper-{version}-update.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()): z.writestr(name, data)
        z.writestr('files.json', json.dumps({name:sha(data) for name,data in files.items()},sort_keys=True))
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    feed = {'schema_version':1,'platform':'windows-x64','version':version,'engine_version':engine_version,
            'archive_url':'https://neptunefrc.com/community/downloads/windows/'+archive.name,
            'archive_sha256':sha(archive.read_bytes()),'archive_size':archive.stat().st_size}
    (output/'latest.json').write_text(json.dumps(feed,indent=2)+'\n')
    (output/'SHA256SUMS.txt').write_text(sha(archive.read_bytes())+'  '+archive.name+'\n')
    return feed

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',required=True);ap.add_argument('--base-feed',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();print(json.dumps(build(args.base,args.base_feed,args.output),indent=2))
