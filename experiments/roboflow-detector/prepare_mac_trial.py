from pathlib import Path
import shutil,hashlib,json,plistlib,ast
root=Path(__file__).resolve().parent
app=root/'Neptune Detector Trial.app'
engine=app/'Contents/Resources/engine'
p=engine/'neptune_yolo.py';s=p.read_text()
def change(a,b):
 global s
 assert s.count(a)==1,(a[:80],s.count(a))
 s=s.replace(a,b)
change("CONTINUITY_REVISION = 'wide-tile-and-gap-continuity-v6'", "CONTINUITY_REVISION = 'robot26-trial-motion-only-v1'")
change("    return Path(os.environ.get('NEPTUNE_ROBOT_MODELS', Path(__file__).with_name('robot-models')))", "    trial = Path(__file__).with_name('trial-robot-models')\n    return trial if trial.is_dir() else Path(os.environ.get('NEPTUNE_ROBOT_MODELS', Path(__file__).with_name('robot-models')))")
change('def crop_box(box, width, height):','def crop_box(box, width, height, box_kind="bumper"):\n    if box_kind == "robot":\n        return [max(0, int(box[0])), max(0, int(box[1])), min(width, int(math.ceil(box[2]))), min(height, int(math.ceil(box[3])))]')
change('def tracker_config(path, fps):','def tracker_config(path, fps, with_reid=True):')
change("'appearance_thresh: 0.8\\nwith_reid: true\\nmodel: auto\\n' % max(1, round(fps*1.5)))", "'appearance_thresh: 0.8\\nwith_reid: %s\\nmodel: auto\\n' % (max(1, round(fps*1.5)), 'true' if with_reid else 'false'))")
change("    colours = bumper_classes(model.names)","    colours = bumper_classes(model.names)\n    box_kind = meta['bumper'].get('box_kind', 'bumper')\n    motion_only = meta['bumper'].get('tracking_mode') == 'motion-only'\n    if motion_only and box_kind != 'robot':\n        raise ValueError('Motion-only trial requires explicitly declared robot boxes.')")
change("    if type(head).__name__ != 'Detect' or getattr(head, 'end2end', False):", "    if not motion_only and (type(head).__name__ != 'Detect' or getattr(head, 'end2end', False)):")
change("config = work/'neptune-botsort.yaml'; tracker_config(config, fps)", "config = work/'neptune-botsort.yaml'; tracker_config(config, fps, with_reid=not motion_only)")
assert s.count("crop_box(d['box'],w,h)")==2
s=s.replace("crop_box(d['box'],w,h)","crop_box(d['box'],w,h,box_kind)")
change("'device': device,\n            'limitations':", "'device': device, 'detector_box_kind':box_kind, 'appearance_reid':not motion_only,\n            'limitations':")
change("'Bumper detections provide expanded chassis crops, not robot segmentation.'", "('Whole-robot detector trial uses motion association without appearance ReID.' if motion_only else 'Bumper detections provide expanded chassis crops, not robot segmentation.')")
ast.parse(s);p.write_text(s)
models=engine/'trial-robot-models';models.mkdir()
original=Path.home()/'Library/Application Support/Neptune Training Helper/robot-models'
manifest=json.loads((original/'manifest.json').read_text())
shutil.copy2(original/manifest['context']['file'], models/manifest['context']['file'])
shutil.copy2(root/'github-candidate/best.pt',models/'robot26-trial.pt')
manifest['bumper']={'file':'robot26-trial.pt','sha256':hashlib.sha256((models/'robot26-trial.pt').read_bytes()).hexdigest(),'box_kind':'robot','tracking_mode':'motion-only'}
manifest['source']={'repository':'ai4funhobby-oss/RobotTracking','path':'runs/detect/robot_detector3/weights/best.pt','purpose':'Experimental robot detector; baseline COCO context retained'}
(models/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Keep the existing engine protocol version while its actual source hashes identify the trial.
import sys
sys.path.insert(0,str(engine));import neptune_engine
(app/'Contents/Resources/engine-identity.json').write_text(json.dumps(neptune_engine.identity(),indent=2)+'\n')
info=app/'Contents/Info.plist';data=plistlib.loads(info.read_bytes())
data['CFBundleDisplayName']='Neptune Detector Trial';data['CFBundleName']='Neptune Detector Trial'
# Keep the account's existing Keychain identity; the separate path distinguishes this local trial.
data['SUEnableAutomaticChecks']=False
data['SUAutomaticallyUpdate']=False
info.write_bytes(plistlib.dumps(data))
print(app)
