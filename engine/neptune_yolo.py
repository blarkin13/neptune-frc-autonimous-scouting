"""Shared, local YOLO/BoT-SORT bumper tracking. No ratings or score-derived identities.

Weights live in a private model bundle, not in public helper base ZIPs. A track ID
is a visual association, never a team number. OCR anchors are kept separately.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

VERSION = 'yolo-botsort-1'
# Bump whenever Identities/recover_segments change: cached tracking is reused only on an exact match.
CONTINUITY_REVISION = 'robot26-reacquisition-ocr3-v2'
ULTRALYTICS_VERSION = '8.4.63'


def bundle_path():
    trial = Path(__file__).with_name('trial-robot-models')
    return trial if trial.is_dir() else Path(os.environ.get('NEPTUNE_ROBOT_MODELS', Path(__file__).with_name('robot-models')))


def bundle(root=None, season=2026):
    root = Path(root) if root else bundle_path()
    path = root/'manifest.json'
    if not path.is_file():
        raise ValueError('Robot tracking model is missing. Download the updated personalized helper, or install the private robot-model bundle on Neptune.')
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1 or season not in data.get('seasons', []):
        raise ValueError('The robot detector has not been configured for this season.')
    for key in ('bumper', 'context'):
        row = data.get(key)
        if not row or not re.fullmatch(r'[A-Za-z0-9_-]+\.pt', row.get('file', '')):
            raise ValueError('Invalid private detector manifest.')
        p = root/row['file']
        if not p.is_file() or p.stat().st_size > 250*1024**2:
            raise ValueError('Robot model file is missing or too large.')
        if hashlib.sha256(p.read_bytes()).hexdigest() != row.get('sha256'):
            raise ValueError('Robot model fingerprint mismatch; reinstall the private model bundle.')
    return data


def fingerprint():
    try:
        data = bundle()
    except (ValueError, OSError):
        return 'model-unavailable'
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def prepare_runtime(progress=print, device='cpu'):
    """Explicit first-run setup, never invoked inside inference or while fitting."""
    bundle()
    cache=Path.home()/'.neptune-trainer/matplotlib';cache.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(cache));os.environ.setdefault('MPLBACKEND','Agg')
    try:
        import importlib.metadata as metadata
        ready = metadata.version('ultralytics') == ULTRALYTICS_VERSION
        for name in ('torch', 'torchvision', 'numpy', 'cv2', 'lap'):
            __import__(name)
    except (ImportError, metadata.PackageNotFoundError):
        ready = False
    if ready:
        return
    progress('Installing robot tracking tools. This is a one-time download; your saved data is kept.')
    # The CPU wheel index avoids pulling NVIDIA libraries onto the low-usage server.
    if device == 'cpu' and sys.platform.startswith('linux'):
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'torch==2.9.1',
                        'torchvision==0.24.1', '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r',
                    str(Path(__file__).with_name('requirements-yolo.txt'))], check=True)


def overlap(a, b):
    """Intersection divided by the smaller area; boxes are xyxy."""
    area = max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))
    return area/max(1e-9, min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])))


def unique_bumpers(detections):
    """Containment NMS: nested boxes on one bumper must not become crowding.

    Keep different colours and spatially separate bumpers. Ordinary IoU NMS
    misses a small duplicate almost entirely contained in a larger prediction.
    """
    kept=[]
    for d in sorted(detections,key=lambda q:q['confidence'],reverse=True):
        a=d['box'];duplicate=False
        for k in kept:
            b=k['box']
            if d['alliance']!=k['alliance']:continue
            aw,ah=a[2]-a[0],a[3]-a[1];bw,bh=b[2]-b[0],b[3]-b[1]
            centered=abs(a[0]+a[2]-b[0]-b[2])/2<=.3*max(aw,bw) and abs(a[1]+a[3]-b[1]-b[3])/2<=.5*max(ah,bh)
            if centered and overlap(a,b)>=.85 and min(aw*ah,bw*bh)/max(aw*ah,bw*bh)>=.25:duplicate=True;break
        if not duplicate:kept.append(d)
    return kept


class Identities:
    """Forward-only OCR anchors. Conflict, crowding, cuts and long gaps clear identity.

    Two exact number reads at least 0.5 s apart establish an identity. Future
    reads never label earlier footage retrospectively. One team per camera/time.
    """
    def __init__(self, roster):
        self.alliance = {int(t): c for c, teams in roster.items() for t in teams}
        self.states = {}
        self.scene = None
        self.serial = 0
        self.invalid_segments = set()

    def update(self, scene, t, detections, reads):
        if scene != self.scene:
            self.states.clear()
            self.scene = scene
        out = []
        for det in detections:
            tid = det['id']
            old = self.states.get(tid)
            crowded = det.get('occluded', False) or any(other['id'] != tid and overlap(det['box'], other['box']) > .35 for other in detections)
            if crowded:
                self.states.pop(tid, None)
                continue
            if old and (t-old['last'] > 1.5 or old['alliance'] != det['alliance']):
                self.states.pop(tid, None)
                old = None
            if old:
                before, now = old['box'], det['box']
                distance = math.hypot((before[0]+before[2]-now[0]-now[2])/2,
                                      (before[1]+before[3]-now[1]-now[3])/2)
                scale = max(before[2]-before[0], now[2]-now[0])
                if distance > max(2*scale, 6*scale*(t-old['last'])):
                    self.states.pop(tid, None)
            if tid not in self.states:
                self.serial += 1
                self.states[tid] = {'last': t, 'alliance': det['alliance'], 'team': None, 'candidate': None, 'moments': [], 'segment':self.serial}
            state = self.states[tid]
            state['last'] = t
            state['box'] = det['box']
            teams = {r['team'] for r in reads if r.get('track') == tid and r.get('kind') == 'exact' and self.alliance.get(r.get('team')) == det['alliance']}
            if len(teams) > 1:
                self.states.pop(tid, None)
                continue
            if teams:
                team = next(iter(teams))
                if state['candidate'] != team:
                    if state['candidate'] is not None:
                        self.invalid_segments.add(state['segment'])
                        self.serial += 1;state['segment']=self.serial
                    state.update(team=None, candidate=team, moments=[])
                if not state['moments'] or t-state['moments'][-1] >= .5:
                    state['moments'].append(t)
                if len(state['moments']) >= 2:
                    state['team'] = team
            if state['team'] is not None:
                out.append(dict(det, team=state['team'], anchor_times=state['moments'][-2:],identity_segment=state['segment']))
        # Refuse duplicate assignments rather than choosing the more convenient robot.
        duplicates = {d['team'] for d in out if sum(q['team'] == d['team'] for q in out) > 1}
        for d in out:
            if d['team'] in duplicates:
                self.states.pop(d['id'], None)
        return [d for d in out if d['team'] not in duplicates]


def recover_segments(points, confirmations, invalid, model_sha):
    """Offline identity verification of an uninterrupted, unambiguous tracker segment.

    Two agreeing OCR anchors may verify earlier frames of that SAME continuous
    segment. Never cross a cut, overlap, large jump, detection gap or conflicting
    read. This is offline verification, not an invented/interpolated position.
    """
    verified={}
    for segment,rows in confirmations.items():
        teams={r['team'] for r in rows};times=sorted({t for r in rows for t in r['anchor_times']})
        if segment in invalid or len(teams)!=1 or len(times)<2 or times[-1]-times[0]<.5:continue
        verified[segment]=(next(iter(teams)),times)
    out=[]
    for p in points:
        identity=verified.get(p['identity_segment'])
        if identity:
            team,times=identity
            out.append(dict(p,team=team,identity_method='yolo_botsort_ocr',identity_evidence={'anchor_times':times,'model_sha256':model_sha,'offline_segment_verified':True}))
    # Duplicate identities in a camera/frame remain ambiguous, even offline.
    counts={}
    for p in out:
        key=(p['camera'],p['scene'],p['t'],p['team']);counts[key]=counts.get(key,0)+1
    return [p for p in out if counts[(p['camera'],p['scene'],p['t'],p['team'])]==1]


def bumper_classes(names):
    aliases = {'red': 'red', 'blue': 'blue', 'red-bumper': 'red', 'blue-bumper': 'blue'}
    result = {int(k): aliases.get(str(v).lower()) for k, v in names.items()}
    if not result or None in result.values() or set(result.values()) != {'red', 'blue'}:
        raise ValueError('This detector must identify red and blue FRC bumpers; a generic COCO model cannot replace it.')
    return result


def crop_box(box, width, height, box_kind="bumper"):
    if box_kind == "robot":
        return [max(0, int(box[0])), max(0, int(box[1])), min(width, int(math.ceil(box[2]))), min(height, int(math.ceil(box[3])))]
    """A bumper is not a complete robot: keep this expanded chassis crop explicit."""
    x0, y0, x1, y1 = box
    w, h = x1-x0, y1-y0
    return [max(0, int(x0-.3*w)), max(0, int(y0-2*h)),
            min(width, int(math.ceil(x1+.3*w))), min(height, int(math.ceil(y1+.4*h)))]


def tracker_config(path, fps, with_reid=True):
    # Ultralytics sets frame_rate=30 internally for ndarray inputs. Convert seconds
    # to the sampled frame count so CPU mode and GPU mode retain the same gap.
    path.write_text('tracker_type: botsort\ntrack_high_thresh: 0.3\ntrack_low_thresh: 0.1\n'
                    'new_track_thresh: 0.4\ntrack_buffer: %d\nmatch_thresh: 0.7\n'
                    'fuse_score: true\ngmc_method: sparseOptFlow\nproximity_thresh: 0.5\n'
                    'appearance_thresh: 0.8\nwith_reid: %s\nmodel: auto\n' % (max(1, round(fps*1.5)), 'true' if with_reid else 'false'))


def native_ocr_width(source_width,bounds,working_width):
    native=max(2,2*round(source_width*(bounds[2]-bounds[0])/2))
    return native if native>working_width*1.25 else None

def scaled_ocr_box(box,working_size,native_size):
    w,h=working_size;W,H=native_size
    return [max(0,int(math.floor(box[0]*W/w))),max(0,int(math.floor(box[1]*H/h))),
            min(W,int(math.ceil(box[2]*W/w))),min(H,int(math.ceil(box[3]*H/h)))]


def tile_starts(length, size, overlap=.25):
    """Cover a native-resolution panel with overlapping tiles, including its far edge."""
    if length <= size:return [0]
    step=max(1,round(size*(1-overlap)))
    return sorted(set(range(0,length-size+1,step)) | {length-size})


def tiled_bumpers(detector,image,colours,device,tile_width=960):
    """Supplement a full-panel pass with native-pixel wide-shot bumper candidates."""
    height,width=image.shape[:2]
    candidates=[]
    for left in tile_starts(width,min(tile_width,width)):
        crop=image[:,left:left+min(tile_width,width)]
        result=detector.predict(crop,device=device,imgsz=960,conf=.16,iou=.5,max_det=12,verbose=False,save=False)[0]
        boxes=result.boxes
        if boxes is None:continue
        for xyxy,cls,conf in zip(boxes.xyxy.cpu().tolist(),boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist()):
            alliance=colours.get(int(cls))
            x0,y0,x1,y1=xyxy
            box=[max(0.,left+x0),max(0.,y0),min(float(width),left+x1),min(float(height),y1)]
            if alliance and x1>x0 and y1>y0 and box[2]>box[0] and box[3]>box[1]:
                candidates.append({'box':box,'alliance':alliance,'confidence':float(conf),'box_source':'tiled_detector'})
    return unique_bumpers(candidates)


def merge_tiled_bumpers(detections,candidates,working_size,native_size):
    """Add only distinct, nonconflicting tile detections in working-frame pixels."""
    w,h=working_size;W,H=native_size
    kept=list(detections);added=0
    for candidate in sorted(candidates,key=lambda d:d['confidence'],reverse=True):
        box=[max(0.,min(float(w),candidate['box'][i]*(w/W if i%2==0 else h/H))) for i in range(4)]
        if box[2]<=box[0] or box[3]<=box[1]:continue
        if any(overlap(box,d['box'])>.45 for d in kept):continue
        # A nearby opposite-colour prediction is ambiguous, not an extra robot.
        if any(d['alliance']!=candidate['alliance'] and overlap(box,d['box'])>.20 for d in kept):continue
        kept.append({'id':None,'alliance':candidate['alliance'],'box':box,
                     'confidence':candidate['confidence'],'box_source':'tiled_detector'})
        added+=1
    return kept,added


def _track_camera(video, facts, profile, backend, work, fps=6., width=960, read_every=.5, progress=None, camera=None):
    import importlib.metadata
    if importlib.metadata.version('ultralytics') != ULTRALYTICS_VERSION:
        raise ValueError('Robot tracking runtime needs the updated helper setup (ultralytics '+ULTRALYTICS_VERSION+').')
    import numpy as np
    import cv2
    import torch
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    from ultralytics import YOLO
    from neptune_tracking import wide_band, decode, read_position, coverage, FRAME_DECODER_REVISION
    from neptune_facts import roster_match
    meta = bundle(season=int(profile['season']))
    root = bundle_path()
    model = YOLO(str(root/meta['bumper']['file']))
    colours = bumper_classes(model.names)
    box_kind = meta['bumper'].get('box_kind', 'bumper')
    motion_only = meta['bumper'].get('tracking_mode') == 'motion-only'
    if motion_only and box_kind != 'robot':
        raise ValueError('Motion-only trial requires explicitly declared robot boxes.')
    duplicate_counts={'removed':0}
    def deduplicate_before_tracking(predictor):
        # Registered BEFORE Ultralytics adds its tracker callback: each physical
        # bumper should enter BoT-SORT once, rather than compete with its clones.
        for result in predictor.results:
            boxes=result.boxes
            if boxes is None or not len(boxes):continue
            records=[{'index':i,'box':box,'alliance':int(cls),'confidence':float(conf)} for i,(box,cls,conf) in enumerate(zip(boxes.xyxy.cpu().tolist(),boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist()))]
            kept=unique_bumpers(records);duplicate_counts['removed']+=len(records)-len(kept)
            indices=[r['index'] for r in kept]
            feats=getattr(result,'feats',None)
            if feats is not None:
                result.feats=[feats[i] for i in indices] if isinstance(feats,(list,tuple)) else feats[indices]
            result.update(boxes=boxes.data[indices])
    model.add_callback('on_predict_postprocess_end',deduplicate_before_tracking)

    # Require native detector features: don't silently download a people ReID model.
    head = model.model.model[-1]
    if not motion_only and (type(head).__name__ != 'Detect' or getattr(head, 'end2end', False)):
        raise ValueError('The detector does not expose native appearance features for BoT-SORT.')
    context = YOLO(str(root/meta['context']['file']))
    person = [int(k) for k, v in context.names.items() if v == 'person']
    if not person:
        raise ValueError('The context detector has no person class.')
    device = os.environ.get('NEPTUNE_TRACKING_DEVICE', 'auto')
    if device == 'auto':
        device = 'mps' if torch.backends.mps.is_available() else '0' if torch.cuda.is_available() else 'cpu'
    if device == 'cpu':
        torch.set_num_threads(1)
        fps = min(fps, 3.)
    if not 1 <= fps <= 15 or not 320 <= width <= 1920:
        raise ValueError('Invalid robot tracking sampling settings.')
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    config = work/'neptune-botsort.yaml'; tracker_config(config, fps, with_reid=not motion_only)
    periods = [p for k, p in facts['periods'].items() if k in ('auto', 'teleop') and p]
    if not periods:
        raise ValueError('Robot tracking needs observed match periods.')
    start, end = max(0., min(p['start'] for p in periods)), min(facts['source']['duration_s'], max(p['end'] for p in periods))
    if end <= start:
        raise ValueError('Match periods fall outside the video.')
    bounds=camera['bounds'] if camera else [0.,*wide_band(profile)[:1],1.,wide_band(profile)[1]]
    left,top,right,bottom=bounds;band=(top,bottom)
    roster = {c: [int(t) for t, value in facts['bumpers']['identities'].items() if value['alliance'] == c] for c in ('red', 'blue')}
    resolver = Identities(roster); teams = set(roster['red']+roster['blue'])
    from neptune_reacquisition import Reacquisition
    reacquisition=Reacquisition();reacquisition_rows=[]
    scene = 0; cuts = []; previous = None; localizations = []; anchors = []; frame_count = 0; visual_tracks = set()
    segment_points=[];confirmations={};observations=[]
    from neptune_box_follow import BoxFollower
    from neptune_review_learning import descriptor
    follower=BoxFollower(max_gap=max(.75,read_every+1/fps))
    sample_step=max(1,round(fps*read_every))
    probe=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width','-of','csv=p=0',str(video)],text=True,timeout=30)
    ocr_width=native_ocr_width(int(probe.strip().splitlines()[0]),bounds,width)
    hires=decode(video,*band,start,end,fps/sample_step,ocr_width,left=left,right=right) if ocr_width else None
    tile_model=YOLO(str(root/meta['bumper']['file'])) if hires is not None and (camera is None or camera['name']=='wide') else None
    tile_counts={'frames':0,'candidates':0,'added':0}
    people = []; ocr_folder = work/'yolo-ocr'; ocr_folder.mkdir(exist_ok=True)
    try:
        for t, w, h, y, u, v in decode(video, *band, start, end, fps, width, left=left, right=right):
            frame_count += 1
            sample = (frame_count-1) % sample_step == 0
            if progress and frame_count % max(1, round(fps*10)) == 0:
                progress('Tracking robot identities: %d of %d video seconds processed' % (t-start, end-start))
            gray = np.frombuffer(y, dtype=np.uint8).reshape(h, w)
            small = cv2.resize(gray, (32, 16)).astype('float32')
            cut = previous is not None and float(np.mean(np.abs(previous-small))) > 38
            previous = small
            if cut:
                scene += 1; cuts.append(round(t, 3)); people = []
                for tracker in getattr(getattr(model, 'predictor', None), 'trackers', []):
                    tracker.reset()
            planes = np.stack([gray, np.frombuffer(u, dtype=np.uint8).reshape(h, w), np.frombuffer(v, dtype=np.uint8).reshape(h, w)], axis=2)
            image = cv2.cvtColor(planes, cv2.COLOR_YUV2BGR)
            results = model.track(image, persist=True, tracker=str(config), device=device, imgsz=960, conf=.1, iou=.5, max_det=12, verbose=False, save=False)
            dets = []
            boxes = results[0].boxes
            if boxes is not None:
                ids=boxes.id.cpu().tolist() if boxes.id is not None else [None]*len(boxes)
                for xyxy, cls, conf, tid in zip(boxes.xyxy.cpu().tolist(), boxes.cls.cpu().tolist(), boxes.conf.cpu().tolist(), ids):
                    box = [max(0., min(float(a), float(w if i % 2 == 0 else h))) for i, a in enumerate(xyxy)]
                    if int(box[2]) <= int(box[0]) or int(box[3]) <= int(box[1]) or int(cls) not in colours:
                        continue
                    dets.append({'id': int(tid) if tid is not None else None, 'alliance': colours[int(cls)], 'box': box, 'confidence': float(conf)})
                    if tid is not None:visual_tracks.add((scene, int(tid)))
            ocr_image=image
            if sample and hires is not None:
                try:th,W,H,Y,U,V=next(hires)
                except StopIteration:raise ValueError('Native OCR stream ended before the tracking sample')
                if abs(th-t)>.5/fps:raise ValueError('Native OCR frame is not aligned to the tracking sample')
                ocr_image=cv2.cvtColor(np.stack([np.frombuffer(q,dtype=np.uint8).reshape(H,W) for q in (Y,U,V)],axis=2),cv2.COLOR_YUV2BGR)
            if sample and tile_model is not None:
                candidates=tiled_bumpers(tile_model,ocr_image,colours,device)
                tile_counts['frames']+=1;tile_counts['candidates']+=len(candidates)
                dets,added=merge_tiled_bumpers(dets,candidates,(w,h),(ocr_image.shape[1],ocr_image.shape[0]))
                tile_counts['added']+=added
            dets=follower.update(gray,t,scene,dets)
            if sample or cut:
                cr = context.predict(image, device=device, imgsz=640, classes=person, conf=.5, verbose=False, save=False)[0]
                people = cr.boxes.xyxy.cpu().tolist() if cr.boxes is not None else []
            for d in dets:
                d['occluded'] = any(overlap(d['box'], p) > .65 for p in people)
            reads = []
            # Existing OCR is authoritative only when its centre lands uniquely on
            # this same camera's detected bumper, never another panel or queue robot.
            for r in facts['bumpers'].get('reads', []):
                if abs(r['t']-t) > .5/fps or r.get('kind') != 'exact' or not r.get('frame_box'):
                    continue
                pos = read_position(r, band, profile['camera_top'], w/(right-left), h)
                if pos is not None:pos=(pos[0]-left*w/(right-left),pos[1])
                if pos is not None and not 0<=pos[0]<=w:pos=None
                if pos is None:
                    continue
                hits = [d for d in dets if d['alliance'] == resolver.alliance.get(r.get('team')) and d['box'][0] <= pos[0] <= d['box'][2] and d['box'][1] <= pos[1] <= d['box'][3]]
                if len(hits) == 1:
                    reads.append({'track': hits[0]['id'], 'team': r['team'], 'kind': 'exact'})
            if sample:
                paths = []
                for d in dets:
                    if d.get('box_source')=='optical_flow':continue
                    a,b,c,e=scaled_ocr_box(d['box'],(w,h),(ocr_image.shape[1],ocr_image.shape[0]))
                    path = ocr_folder/('bumper-%d.png' % d['id'])
                    cv2.imwrite(str(path), cv2.resize(ocr_image[b:e, a:c], None, fx=3, fy=3))
                    paths.append((d, path))
                texts = backend.recognize([p for d, p in paths]) if paths else {}
                for d, path in paths:
                    for token in texts.get(str(path), []):
                        for word in re.findall(r'\S+', token['t']):
                            matched = roster_match(word, teams)
                            if matched and matched[0] == 'exact':
                                reads.append({'track': d['id'], 'team': matched[1], 'kind': 'exact'})
                    path.unlink(missing_ok=True)
            proposals=reacquisition.propose(scene,t,dets,resolver.states,reads,width=w)
            reacquisition_rows.extend(dict(p,camera=camera['name'] if camera else 'wide') for p in proposals)
            # Retain unassigned detections for offline reconciliation and human review,
            # including contact frames the strict training resolver intentionally rejects.
            for d in dets:
                a,b,c,e=crop_box(d['box'],w,h,box_kind)
                observations.append({'t':round(t,4),'box':[left+a/w*(right-left),band[0]+b/h*(band[1]-band[0]),(c-a)/w*(right-left),(e-b)/h*(band[1]-band[0])],
                    'track_id':d['id'],'alliance':d['alliance'],'scene':(camera['name']+':'+str(scene)) if camera else scene,
                    'camera':camera['name'] if camera else 'wide','camera_bounds':list(bounds),
                    'read_teams':sorted({r['team'] for r in reads if r['track']==d['id']}),
                    'detection_confidence':round(d['confidence'],4),'occluded':d.get('occluded',False),
                    'box_source':d.get('box_source','detector'),'flow_support':d.get('flow_support'),
                    'appearance':descriptor(image,[a,b,c-a,e-b])})
            # Flow can keep a visible box alive but never supplies an OCR verification segment.
            identified=resolver.update(scene,t,[d for d in dets if d.get('box_source')!='optical_flow'],reads)
            for d in identified:
                segment=d['identity_segment'];confirmations.setdefault(segment,[]).append({'team':d['team'],'anchor_times':d['anchor_times']})
            for d in dets:
                state=resolver.states.get(d['id'])
                if not state or abs(state['last']-t)>.001:continue
                a,b,c,e=crop_box(d['box'],w,h,box_kind)
                segment_points.append({'t':round(t,4),'box':[left+a/w*(right-left),band[0]+b/h*(band[1]-band[0]),(c-a)/w*(right-left),(e-b)/h*(band[1]-band[0])],
                    'bumper_box':d['box'],'identity_segment':state['segment'],'track_id':d['id'],'scene':(camera['name']+':'+str(scene)) if camera else scene,
                    'camera':camera['name'] if camera else 'wide','camera_bounds':list(bounds),'detection_confidence':round(d['confidence'],4)})
            anchors.extend(dict(r, t=round(t, 4), scene=scene) for r in reads)
    finally:
        if hires is not None:hires.close()
        for p in ocr_folder.glob('bumper-*.png'):
            p.unlink(missing_ok=True)
    localizations=recover_segments(segment_points,confirmations,resolver.invalid_segments,meta['bumper']['sha256'])
    verified={(p['track_id'],p['t']):p['team'] for p in localizations}
    for p in observations:p['verified_team']=verified.get((p['track_id'],p['t']))
    points = {team: [(s['t'],) for s in localizations if s['team'] == team] for team in teams}
    return {'status': 'measured', 'version': VERSION, 'model_fingerprint': fingerprint(), 'model_source': meta['source'],
            'box_following':follower.diagnostics,'wide_tile_detection':tile_counts,'ocr_width':ocr_width or width,'observations':observations,'decoder_revision':FRAME_DECODER_REVISION,'duplicate_bumper_boxes_removed':duplicate_counts['removed'],'anchors':anchors,'continuity_revision':CONTINUITY_REVISION,'fps': fps, 'band': list(band), 'start': start, 'end': end, 'scene_cuts': cuts, 'localizations': localizations,
            'coverage': {str(k): v for k, v in coverage(points, start, end).items()}, 'tracks': len({(s['scene'], s['track_id']) for s in localizations}),
            'frames_processed': frame_count, 'visual_tracks': len(visual_tracks), 'bumper_anchors': len(anchors), 'device': device, 'ocr_every_processed_frames':sample_step, 'reacquisition_proposals':reacquisition_rows, 'detector_box_kind':box_kind, 'appearance_reid':not motion_only,
            'limitations': [('Whole-robot detector trial uses motion association without appearance ReID.' if motion_only else 'Bumper detections provide expanded chassis crops, not robot segmentation.'), 'Identity is cleared on ambiguous overlap, camera cuts and long detection gaps.',
                            'Tracks alone do not establish successful scoring, climb outcomes or points.']}


def camera_views(profile):
    """Each broadcast panel has its own tracker; identities never jump panels."""
    from neptune_tracking import wide_band
    configured=profile.get('camera_views')
    if configured:
        views=[dict(name=str(v['name']),bounds=list(v['bounds'])) for v in configured]
    else:
        top,bottom=wide_band(profile)
        views=[{'name':'wide','bounds':[0.,top,1.,bottom]}]
        if 'closeup_top' in profile:
            seam=profile['camera_top']+(1-profile['camera_top'])*profile['closeup_top']
            split=profile.get('closeup_split',.5)
            views.extend([{'name':'closeup-left','bounds':[0.,seam,split,1.]},
                          {'name':'closeup-right','bounds':[split,seam,1.,1.]}])
    for v in views:
        a,b,c,d=v['bounds']
        if not all(isinstance(x,(int,float)) for x in (a,b,c,d)) or not 0<=a<c<=1 or not profile['camera_top']<=b<d<=1:raise ValueError('Invalid independent camera bounds.')
    if len({v['name'] for v in views})!=len(views):raise ValueError('Camera names must be unique.')
    return views


def track_match(video,facts,profile,backend,work,fps=6.,width=960,read_every=.5,progress=None):
    from neptune_tracking import coverage
    all_points=[];all_anchors=[];all_observations=[];results=[]
    for camera in camera_views(profile):
        if progress:progress('Tracking robot identities in '+camera['name'])
        result=_track_camera(video,facts,profile,backend,Path(work)/camera['name'],fps,width,read_every,progress,camera)
        result['camera']=camera['name'];result['camera_bounds']=camera['bounds'];results.append(result)
        all_points.extend(result['localizations']);all_anchors.extend(result.get('anchors',[]));all_observations.extend(result.get('observations',[]))
    out=dict(results[0]);out.update(camera_engine='independent-camera-views-v4',localizations=sorted(all_points,key=lambda p:(p['t'],p['camera'],p['team'])),anchors=all_anchors,
        camera_cuts={r['camera']:r['scene_cuts'] for r in results},cameras=[{'name':r['camera'],'bounds':r['camera_bounds'],'frames_processed':r['frames_processed'],'tracks':r['tracks'],'duplicate_bumper_boxes_removed':r['duplicate_bumper_boxes_removed']} for r in results],
        frames_processed=sum(r['frames_processed'] for r in results),tracks=sum(r['tracks'] for r in results),visual_tracks=sum(r['visual_tracks'] for r in results),bumper_anchors=sum(r['bumper_anchors'] for r in results))
    teams={int(k) for k in facts['bumpers']['identities']}
    out['coverage']={str(k):v for k,v in coverage({team:[(s['t'],) for s in all_points if s['team']==team] for team in teams},out['start'],out['end']).items()}
    if all_observations:
        from neptune_identity import reconcile
        roster={c:[int(t) for t,v in facts['bumpers']['identities'].items() if v['alliance']==c] for c in ('red','blue')}
        from neptune_review_learning import active_association
        association=active_association();out['association_sha']=hashlib.sha256(json.dumps(association,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        out['identity_review']=reconcile(all_observations,roster,facts['source']['sha256'],association=association)
    out['reacquisition_proposals']=[p for r in results for p in r.get('reacquisition_proposals',[])]
    out['observations']=all_observations
    return out
