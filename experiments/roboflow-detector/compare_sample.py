from pathlib import Path
import os,sys,json,time
root=Path(__file__).resolve().parent
os.environ['YOLO_AUTOINSTALL']='false';os.environ['MPLCONFIGDIR']='/tmp/neptune-trial-matplotlib';os.environ['YOLO_CONFIG_DIR']='/tmp/neptune-trial-ultralytics'
import cv2,torch
from ultralytics import YOLO
video=Path.home()/'.neptune-trainer/identity-reviews/2026txcmp1_qm3/media/ZlnweItn8ww.mp4'
cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);n=cap.get(cv2.CAP_PROP_FRAME_COUNT)
frames=[]
for f in [.3,.5,.7]:
 cap.set(cv2.CAP_PROP_POS_FRAMES,int(n*f));ok,image=cap.read()
 if ok: frames.append((f,image))
cap.release()
assert len(frames)==3
paths={'baseline':Path.home()/'Library/Application Support/Neptune Training Helper/robot-models/best_bumper_model.pt','candidate':root/'github-candidate/best.pt'}
result={'device':'mps' if torch.backends.mps.is_available() else 'cpu','video':video.name,'note':'Full-frame sample detections only. Counts are not accuracy or verified identities.','models':{}}
for label,path in paths.items():
 model=YOLO(str(path));rows=[]
 for f,image in frames:
  t=time.monotonic();r=model.predict(image,imgsz=960,device=result['device'],conf=.16,max_det=30,verbose=False)[0]
  rows.append({'video_fraction':f,'detections':len(r.boxes),'seconds':round(time.monotonic()-t,3)})
  if f==.5: cv2.imwrite(str(root/(label+'-sample.jpg')),r.plot())
 result['models'][label]={'classes':model.names,'samples':rows}
print(json.dumps(result,indent=2));(root/'sample-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
