#!/usr/bin/env python3
"""Create review artifacts only; never deploy, reset data or include credentials/weights."""
from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
R=Path(__file__).resolve().parents[1];B=R/'.helper-build/native';O=R.parent/'Neptune-Native-Mac-3.0.3';O.mkdir(exist_ok=True)
base=json.loads((B/'review-base.json').read_text());base.update(json.loads((B/'game-actions-review-base.json').read_text()));base.update(json.loads((B/'cleanup-review-base.json').read_text()));paths=list(base)+['neptune_secure/community-training-pairing.php','public_html/Neptune/community/connect-training.php']
for n in paths:
 if n.endswith('.php'):subprocess.run(['php','-l',str(R/n)],check=True,stdout=subprocess.DEVNULL)
with zipfile.ZipFile(O/'Neptune_Native_Mac_and_Tracking_v3.0.3_Maintenance.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in paths:z.write(R/name,name)
 z.writestr('neptune-package.json',json.dumps({'base':{p:base.get(p) for p in paths}},indent=2))
source=[]
source.extend(p for p in (R/'macos/NeptuneTrainingHelper').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
source.extend(p for p in (R/'helper').iterdir() if p.is_file() and p.suffix in ('.py','.json','.txt'))
source.extend(p for p in (R/'helper/vision').glob('*') if p.is_file())
source.extend(R/'scripts'/n for n in ['build-native-mac.py','build-native-dmg.py','build-native-ffmpeg.sh','fetch-native-mac-deps.py','publish-native-mac.py','test-native-mac-runtime.py','package-native-mac-review.py','build-training-computers.py','build-helper-installers.py'])
source.extend(R/name for name in paths)
source.extend(R/'tests/community-analysis'/name for name in ('training-pairing.php','pairing.php','training-computers.php','game-action-contract.php','game-action-export.php','progress-recovery.cjs'))
with zipfile.ZipFile(O/'Neptune-Native-Mac-3.0.3-source.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(set(source)):z.write(p,str(p.relative_to(R)))
# Companion AWS package uses the same engine files as the Mac app.
engine_names=('neptune_cache.py','neptune_page_worker.py','neptune_scoring_model.py','neptune_training.py','neptune_engine.py','neptune_yolo.py','neptune_temporal.py','neptune_action_labels.py','neptune_video_labels.py','neptune_events.py','neptune_trainer.py')
with zipfile.ZipFile(O/'Neptune_Server_Engine_2.2.4_Update.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in engine_names:z.write(R/'neptune_secure/community-learning'/n,'neptune_secure/community-learning/'+n)
qa=O/'verification';qa.mkdir(exist_ok=True)
for name in ['disposable-media-tests.txt','cleanup-embedded-tests.txt','cleanup-php-tests.txt','all-python-tests.txt','pairing-tests.txt','legacy-pairing-tests.txt','training-api-tests.txt','embedded-runtime-tests.txt','update-interruption.json','game-action-python-regression.txt','game-action-php-regression.txt','game-action-page-control-tests.txt','game-action-export-tests.txt','game-action-embedded-tests.txt']:
 if (B/name).exists():shutil.copy2(B/name,qa/name)
for folder,name in [('ct9-continuity-v4','comparison.json'),('ct9-continuity-v4','label-readiness.json'),('real-fresh-cache-check','verification.json')]:
 if (B/folder/name).exists():shutil.copy2(B/folder/name,qa/(folder+'-'+name))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(O/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+str(p.relative_to(O))+'\n' for p in sorted(O.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'))
print('Review artifacts:',O)
