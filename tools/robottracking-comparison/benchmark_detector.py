"""Evaluate an isolated RobotTracking checkpoint on a frozen reviewed Q4 reference.
No training, label writes, threshold search or model adoption. Uses Neptune's existing gate metric.
"""
import argparse,hashlib,importlib,json,os,time
from pathlib import Path
from unittest.mock import patch


def safe_candidate(path):
    import torch
    from ultralytics import YOLO
    import ultralytics.nn.tasks as tasks
    allowed=[]
    for name in torch.serialization.get_unsafe_globals_in_checkpoint(path):
        if not name.startswith(('ultralytics.nn.','torch.nn.')) and name != 'builtins.set':
            raise ValueError('Unexpected checkpoint global: '+name)
        module,attr=name.rsplit('.',1);allowed.append(getattr(importlib.import_module(module),attr))
    with torch.serialization.safe_globals(allowed):
        checkpoint=torch.load(path,map_location='cpu',weights_only=True)
    with patch.object(tasks,'torch_safe_load',return_value=(checkpoint,str(path))):
        return YOLO(str(path))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--engine',type=Path,required=True);args=ap.parse_args()
    import sys
    sys.path.insert(0,str(args.engine))
    import torch,cv2,ultralytics
    import neptune_robot_jobs as jobs
    torch.set_num_threads(2)
    ref=json.loads(args.reference.read_text());assert ref['match_key']=='2026txcmp1_qm4'
    args.output.mkdir(exist_ok=True,parents=True)
    candidate=args.source/'runs/detect/robot_detector3/weights/best.pt';current=jobs.current_wide_weights()
    report={'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),'reference_match':ref['match_key'],'frames':len(ref['frames']),'iou':.3,'confidence':.25,'metric':'existing Neptune class-agnostic one-to-one gate metric','device':'cpu','threads':2,'ultralytics':ultralytics.__version__,'torch':torch.__version__,'experiments':[],'adopted':False,'limitations':['Q4 development diagnostic, not an untouched independent benchmark.','Candidate training overlap with Q4 is not independently established.','Detection comparison only; does not establish robot identity or action accuracy.']}
    for label,path,sizes in [('neptune_current',current,[1280]),('robottracking_candidate',candidate,[640,1280])]:
        model=safe_candidate(path)
        names={int(k):str(v) for k,v in model.names.items()};print(label,names,flush=True)
        if not all(any(c in n.lower() for c in ('red','blue')) for n in names.values()):raise ValueError('Unexpected candidate classes: '+str(names))
        for size in sizes:
            totals={'wide':[0,0,0],'closeup':[0,0,0]};predictions=[];wall=time.perf_counter();inference=0.
            for i,row in enumerate(ref['frames']):
                image=cv2.imread(str(args.reference.parent/row['image']));h,w=image.shape[:2]
                start=time.perf_counter();result=model.predict(image,imgsz=size,conf=.25,device='cpu',verbose=False)[0];inference+=time.perf_counter()-start
                pred=[]
                for box,cls,confidence in zip(result.boxes.xyxy.tolist(),result.boxes.cls.tolist(),result.boxes.conf.tolist()):
                    x0,y0,x1,y1=box;pred.append({'box':[x0/w,y0/h,x1/w,y1/h],'alliance':'red' if 'red' in names[int(cls)].lower() else 'blue','confidence':confidence})
                truth=[[b['x'],b['y'],b['x']+b['w'],b['y']+b['h']] for b in row['boxes']]
                for band,values in jobs.score(truth,[p['box'] for p in pred]).items():totals[band]=[a+b for a,b in zip(totals[band],values)]
                predictions.append({'t_ms':row['t_ms'],'image':row['image'],'predictions':pred})
                if i%10==0:print(f'{label} {size}: {i+1}/{len(ref["frames"])}',flush=True)
            def summary(v):
                m,t,p=v;precision=m/p if p else 0;recall=m/t if t else 0
                return {'matched':m,'bumpers':t,'detections':p,'missed':t-m,'false_positives':p-m,'precision':precision,'recall':recall,'f1':2*m/(t+p) if t+p else 0}
            experiment={'label':label,'image_size':size,'weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'classes':names,'overall':summary([sum(v[i] for v in totals.values()) for i in range(3)]),'by_view':{k:summary(v) for k,v in totals.items()},'wall_seconds':time.perf_counter()-wall,'inference_seconds':inference,'predictions_file':f'{label}-{size}-predictions.json'}
            (args.output/experiment['predictions_file']).write_text(json.dumps(predictions))
            report['experiments'].append(experiment);(args.output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(experiment),flush=True)
        del model
    print('Finished; no model was adopted.',flush=True)

if __name__=='__main__':main()
