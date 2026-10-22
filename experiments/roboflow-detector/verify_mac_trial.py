from pathlib import Path
import os,sys,json,tempfile
root=Path(__file__).resolve().parent
engine=root/'Neptune Detector Trial.app/Contents/Resources/engine'
os.environ['YOLO_AUTOINSTALL']='false'
os.environ['MPLCONFIGDIR']='/tmp/neptune-trial-matplotlib'
os.environ['YOLO_CONFIG_DIR']='/tmp/neptune-trial-ultralytics'
sys.path.insert(0,str(engine))
import torch, numpy as np
from ultralytics import YOLO
import neptune_yolo as tracking
meta=tracking.bundle();print('Bundle checksum verification passed',flush=True)
model=YOLO(str(tracking.bundle_path()/meta['bumper']['file']))
assert tracking.bumper_classes(model.names)=={0:'blue',1:'red'}
assert meta['bumper']['box_kind']=='robot'
assert tracking.crop_box([10,20,40,50],100,100,'robot')==[10,20,40,50]
print('Classes and robot crop verified; end2end:',model.model.model[-1].end2end,flush=True)
device='mps' if torch.backends.mps.is_available() else 'cpu'
print('Device:',device,flush=True)
with tempfile.TemporaryDirectory() as temp:
 config=Path(temp)/'tracker.yaml';tracking.tracker_config(config,6,with_reid=False)
 assert 'with_reid: false' in config.read_text()
 image=np.zeros((320,640,3),dtype=np.uint8)
 for i in range(2):
  model.track(image,persist=True,tracker=str(config),device=device,imgsz=640,verbose=False,save=False)
 print('Two-frame detector and BoT-SORT smoke test passed',flush=True)
result={'device':device,'classes':model.names,'end2end':bool(model.model.model[-1].end2end),'smoke_test':'passed','full_match_accuracy':'not evaluated'}
(root/'mac-trial-verification.json').write_text(json.dumps(result,indent=2)+'\n')
