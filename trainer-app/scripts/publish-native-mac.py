#!/usr/bin/env python3
"""Prepare a signed HTTPS update feed locally. Does not deploy or upload anything."""
import argparse,subprocess,shutil,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/'.helper-build/native'
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path);p.add_argument('--url',default='https://neptunefrc.com/community/downloads/mac/');a=p.parse_args()
if not a.url.startswith('https://'):p.error('Public release updates require HTTPS.')
a.output.mkdir(parents=True,exist_ok=True);target=a.output/a.archive.name;subprocess.run(['/bin/cp','-c',str(a.archive),str(target)],check=True)
subprocess.run([str(B/'deps/sparkle/bin/generate_appcast'),'--account','neptune-training-helper','--download-url-prefix',a.url,'--maximum-deltas','0',str(a.output)],check=True)
(a.output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in sorted(a.output.iterdir()) if x.is_file() and x.name!='SHA256SUMS.txt'))
print('Prepared signed release files for review:',a.output)
