"""Screen YOLO bumper candidates with local Ollama; output unreviewed site prefill."""
import argparse,base64,hashlib,json,math,time,urllib.request,re
from pathlib import Path
import cv2,numpy as np,torch
from ultralytics import YOLO

SCHEMA={'type':'object','properties':{'verdicts':{'type':'array','items':{'type':'object','properties':{'candidate_id':{'type':'string'},'digits':{'type':'string'},'alliance':{'type':'string','enum':['red','blue','unknown']}},'required':['candidate_id','digits','alliance'],'additionalProperties':False}}},'required':['verdicts'],'additionalProperties':False}
PROMPT='Each labeled tile A, B, etc is a crop of a robot bumper. For every tile, transcribe the visible printed team-number digits and identify the bumper color red or blue. Ignore white outlines. If the number is unreadable, use empty digits. If the bumper color is unclear, use unknown. Do not guess missing digits. Return every candidate_id exactly once with digits and alliance.'

def validate(raw,candidates):
 rows=raw.get('verdicts') if isinstance(raw,dict) else None
 if not isinstance(rows,list) or len(rows)!=len(candidates):raise ValueError('Incomplete screening response')
 result={}
 for r in rows:
  if not isinstance(r,dict) or r.get('candidate_id') not in candidates or r['candidate_id'] in result or not isinstance(r.get('digits'),str) or r.get('alliance') not in ('red','blue','unknown'):raise ValueError('Invalid screening response')
  result[r['candidate_id']]=r
 return result

def classify_one(path,model):
 schema={'type':'object','properties':{'digits':{'type':'string'},'alliance':{'type':'string','enum':['red','blue','unknown']}},'required':['digits','alliance'],'additionalProperties':False}
 prompt='Read the printed team-number digits on this robot bumper and identify the bumper color red or blue. Ignore any white outline. If the number cannot be read, use empty digits. If the bumper color cannot be read, use unknown. Return JSON with digits and alliance.'
 body={'model':model,'stream':False,'format':schema,'messages':[{'role':'user','content':prompt,'images':[base64.b64encode(path.read_bytes()).decode()]}], 'options':{'temperature':0,'num_ctx':2048,'num_predict':96},'keep_alive':'2m'}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as response:r=json.load(response)
 if not r.get('done') or r.get('done_reason')=='length':raise ValueError('Truncated reading')
 value=json.loads(r['message']['content'])
 if not isinstance(value.get('digits'),str) or value.get('alliance') not in ('red','blue','unknown'):raise ValueError('Invalid reading')
 return value,round(r.get('total_duration',0)/1e9,3)


def sheet(image,boxes,path):
 H,W=image.shape[:2];canvas=np.full((2*260,3*340,3),24,np.uint8)
 for index,b in enumerate(boxes):
  x,y,w,h=[b[k] for k in ('x','y','w','h')];cx=(x+w/2)*W;cy=(y+h/2)*H
  width=max(20,w*W*1.25);height=max(12,h*H*1.5)
  a=max(0,int(cx-width/2));c=min(W,int(cx+width/2));top=max(0,int(cy-height*.5));bottom=min(H,int(cy+height*.5))
  crop=image[top:bottom,a:c].copy();assert crop.size
  cv2.rectangle(crop,(int(x*W-a),int(y*H-top)),(int((x+w)*W-a),int((y+h)*H-top)),(255,255,255),1)
  scale=min(320/crop.shape[1],215/crop.shape[0]);crop=cv2.resize(crop,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
  col=index%3;row=index//3;left=col*340+(340-crop.shape[1])//2;yy=row*260+36+(215-crop.shape[0])//2
  canvas[yy:yy+crop.shape[0],left:left+crop.shape[1]]=crop
  cv2.putText(canvas,b['candidate_id'],(col*340+14,row*260+27),cv2.FONT_HERSHEY_SIMPLEX,.85,(255,255,255),2,cv2.LINE_AA)
 cv2.imwrite(str(path),canvas)

def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--model',default='qwen2.5vl:3b');a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=False);root=Path.home()/'.neptune-trainer';manifest=json.loads((root/'robot-detector/manifest.json').read_text());weight=root/'robot-detector'/manifest['by_camera']['wide']['file']
 detector_sha=hashlib.sha256(weight.read_bytes()).hexdigest();assert detector_sha==manifest['by_camera']['wide']['sha256']
 torch.set_num_threads(4);detector=YOLO(str(weight))
 with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as r:models=json.load(r)['models']
 model=next(m for m in models if m['name']==a.model)
 results=[]
 for m in json.loads(a.metadata.read_text()):
  assert m['match_key']!='2026txcmp1_qm7' and re.fullmatch(r'[A-Za-z0-9_-]{11}',m['video_id'])
  video=root/'cache/videos'/(m['video_id']+'.mp4');assert video.is_file();source_sha=hashlib.sha256(video.read_bytes()).hexdigest();cap=cv2.VideoCapture(str(video));duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/cap.get(cv2.CAP_PROP_FPS)
  times=[round(duration*fraction/4)*4 for fraction in (.24,.52)]
  for t in times:
   while any(abs(t*1000-v)<4000 for v in m['saved_times']):t+=4
   cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,image=cap.read();assert ok
   pred=detector.predict(image,imgsz=1280,conf=.15,iou=.5,verbose=False,device='cpu')[0];H,W=image.shape[:2];candidates=[]
   for xyxy,cls,conf in zip(pred.boxes.xyxy.tolist(),pred.boxes.cls.tolist(),pred.boxes.conf.tolist()):
    x,y,c,d=xyxy;name=pred.names[int(cls)].lower();alliance='red' if 'red' in name else 'blue' if 'blue' in name else None
    if not alliance or (y+d)/2/H<.24 or c-x<10 or d-y<4 or c-x>W*.3:continue
    candidates.append({'alliance':alliance,'x':x/W,'y':y/H,'w':(c-x)/W,'h':(d-y)/H,'detector_confidence':round(conf,4)})
   # Include both broadcast-wide and close-up examples when available.
   wide=sorted((b for b in candidates if b['y']+b['h']/2<.65),key=lambda b:-b['detector_confidence'])
   close=sorted((b for b in candidates if b['y']+b['h']/2>=.65),key=lambda b:-b['detector_confidence'])
   selected=wide[:1]+close[:1]
   for b in sorted(candidates,key=lambda b:-b['detector_confidence']):
    if len(selected)>=2:break
    if b not in selected:selected.append(b)
   if not selected:continue
   for i,b in enumerate(selected):b['candidate_id']=chr(65+i)
   prefix=m['match_key']+'-'+str(int(t*1000));cv2.imwrite(str(a.output/(prefix+'.jpg')),image)
   collage=a.output/(prefix+'-candidates.jpg');sheet(image,selected,collage)
   start=time.monotonic();verdicts={};seconds=0
   for b in selected:
    x,y,w,h=[b[k] for k in ('x','y','w','h')];left=max(0,int((x-.1*w)*W));top=max(0,int((y-.2*h)*H));right=min(W,int((x+1.1*w)*W));bottom=min(H,int((y+1.2*h)*H))
    crop=image[top:bottom,left:right];crop=cv2.resize(crop,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
    crop_path=a.output/(prefix+'-'+b['candidate_id']+'.png');cv2.imwrite(str(crop_path),crop)
    value,elapsed=classify_one(crop_path,a.model);verdicts[b['candidate_id']]={'candidate_id':b['candidate_id'],**value};seconds+=elapsed
   verdicts=validate({'verdicts':list(verdicts.values())},{b['candidate_id'] for b in selected})
   for b in selected:
    v=verdicts[b['candidate_id']];b['ollama']=v;b['selected']=bool(re.fullmatch(r'[1-9][0-9]{1,4}',v['digits'].strip())) and v['alliance']==b['alliance'];b['reviewed']=False
   record={**m,'t_ms':int(t*1000),'source_sha256':source_sha,'frame':prefix+'.jpg','contact_sheet':collage.name,'candidates':selected,'model':a.model,'model_digest':model['digest'],'detector_sha256':detector_sha,'screening_seconds':seconds,'wall_seconds':round(time.monotonic()-start,3),'complete':False}
   results.append(record);(a.output/'results.json').write_text(json.dumps(results,indent=2))
   print(m['match_key'],t,'seconds:',sum(b['selected'] for b in selected),'selected of',len(selected),'candidates',seconds,'inference seconds',flush=True)
  cap.release()
 payloads=[]
 for m in json.loads(a.metadata.read_text()):
  frames={str(r['t_ms']):[{k:b[k] for k in ('alliance','x','y','w','h')} for b in r['candidates'] if b['selected']] for r in results if r['video_id']==m['video_id']}
  payloads.append({'video_id':m['video_id'],'match_key':m['match_key'],'match_id':m['match_id'],'frames':frames,'detector':detector_sha+':ollama-screened:'+a.model,
    'selection':{'method':'YOLO proposals with individual-crop Ollama number/color agreement','model':a.model,'model_digest':model['digest'],'human_reviewed':False,'complete':False}})
 (a.output/'prefill.json').write_text(json.dumps(payloads,indent=2));print('READY',a.output/'prefill.json',flush=True)

if __name__=='__main__':main()
