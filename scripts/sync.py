"""Sync with a conflict guard. See sync-to-neptune.sh."""
import hashlib, json, shutil, sys
from pathlib import Path

here, dest = Path(sys.argv[1]), Path(sys.argv[2])
check = '--check' in sys.argv[3:]
skip = {'__pycache__', '.DS_Store'}


def tree(src, out, only=None, exclude=()):
    for p in sorted(src.rglob('*')):
        rel = p.relative_to(src)
        if p.is_dir() or p.is_symlink() or skip & set(rel.parts) or rel.parts[0] in exclude:
            continue
        if only is None or str(rel) in only:
            yield p, out / rel


server_files = set((here / 'engine/SERVER_FILES.txt').read_text().split())
pairs = [
    *tree(here / 'engine', dest / 'helper', exclude=('server_run.py', 'install-server.sh', 'SERVER_FILES.txt')),
    *tree(here / 'engine', dest / 'neptune_secure/community-learning', only=server_files),
    *tree(here / 'server/neptune_secure', dest / 'neptune_secure', exclude=('community-learning',)),
    *tree(here / 'server/public_html', dest / 'public_html'),
    *tree(here / 'server/sql', dest / 'sql'),
    *tree(here / 'tests/server', dest / 'tests/community-analysis'),
    *tree(here / 'docs', dest / 'docs/community-analysis'),
]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path = here / '.sync-manifest'
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
changed, conflicts = [], []
for src, out in pairs:
    key = str(out.relative_to(dest))
    new = sha(src)
    old = sha(out) if out.exists() else None
    if old == new:
        continue
    # The main repo copy changed since the last sync (or was never synced and differs): don't clobber it.
    if old is not None and manifest.get(key) != old:
        conflicts.append(key)
    else:
        changed.append((src, out, key))
for key in conflicts:
    print('CONFLICT (changed in main repo; bring it here first):', key)
for _, _, key in changed:
    print(('would update ' if check else 'update ') + key)
if conflicts:
    sys.exit(1)
if not check:
    for src, out, key in changed:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    manifest.update({str(out.relative_to(dest)): sha(src) for src, out in pairs})
    manifest_path.write_text(json.dumps(manifest, indent=0, sort_keys=True))
if not changed:
    print('in sync')
