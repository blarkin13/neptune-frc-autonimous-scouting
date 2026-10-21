#!/usr/bin/env python3
"""Build a drag-to-Applications disk image. Does not install or publish it."""
import argparse,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('app',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='neptune-dmg-',dir=str(a.output.parent)) as tmp:
 stage=Path(tmp);subprocess.run(['/bin/cp','-cR',str(a.app),str(stage/a.app.name)],check=True);(stage/'Applications').symlink_to('/Applications')
 (stage/'Read Me.txt').write_text('Drag Neptune Training Helper into Applications, then open it there.\nClick Connect / Reconnect and approve this Mac in Neptune.\nIf macOS blocks this unsigned app, use Privacy & Security > Open Anyway.\nKeychain access uses your Mac login password to read the saved Neptune connection.\nNever disable Gatekeeper or send a password to support.\n')
 subprocess.run(['/usr/bin/hdiutil','create','-volname','Neptune Training Helper','-srcfolder',str(stage),'-format','UDZO','-ov',str(a.output)],check=True)
print(a.output)
