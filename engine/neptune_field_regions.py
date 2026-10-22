"""Source-bound field geometry supporting action predictions, never proving scores."""
import bisect,hashlib,json,math
from pathlib import Path
VERSION='source-bound-field-context-v1'
KINDS={'scoring_target','scoring_zone','feeding_zone','collection_zone','field_boundary','field_calibration'}

def validate(d):
    if d.get('contract')!='neptune-field-regions-v1' or d.get('schema_version')!=1 or d.get('coordinate_system')!='normalized_full_video_frame' or d.get('time_basis')!='video_elapsed_ms':raise ValueError('Unsupported field-region contract')
    if not isinstance(d.get('regions'),list) or len(d['regions'])>500:raise ValueError('Invalid region count')
    for r in d['regions']:
        ps=r.get('points',[])
        if r.get('kind') not in KINDS or r.get('camera_view') not in {'wide','closeup-left','closeup-right','other'} or r.get('alliance') not in {'red','blue','neutral'} or r.get('reviewed') is not True:raise ValueError('Invalid region metadata')
        if not 3<=len(ps)<=100 or any(not isinstance(p,list) or len(p)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in p) for p in ps):raise ValueError('Invalid normalized polygon')
        ts=[r.get(k) for k in ('start_ms','reference_ms','end_ms')]
        if any(type(t) not in (int,float) or not math.isfinite(t) for t in ts) or not 0<=ts[0]<=ts[1]<=ts[2]:raise ValueError('Invalid time interval')
        if not isinstance(r.get('game_key'),str) or not r['game_key']:raise ValueError('Missing game key')
    from neptune_homography import calibrate
    for r in d['regions']:
        if r['kind']=='field_calibration':calibrate(r['points'])
    return d

def inside(point,polygon):
    x,y=point;hit=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        ax,ay=a;bx,by=b
        cross=(x-ax)*(by-ay)-(y-ay)*(bx-ax)
        if abs(cross)<1e-10 and min(ax,bx)<=x<=max(ax,bx) and min(ay,by)<=y<=max(ay,by):return True
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:hit=not hit
    return hit

def load(facts,game_key,root=None):
    sha=facts.get('source',{}).get('sha256','')
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):return None
    folder=Path(root) if root else Path.home()/'.neptune-trainer/field-regions'
    path=folder/(sha+'.json')
    if not root and not path.is_file():path=Path(__file__).with_name('field-regions')/(sha+'.json')
    if not path.is_file():return None
    d=validate(json.loads(path.read_text()))
    if d.get('source_sha256')!=sha:raise ValueError('Region source checksum mismatch')
    d=dict(d,regions=[r for r in d['regions'] if r['game_key']==game_key])
    return d

def active(r,t,camera,facts):
    if r['camera_view']!=camera or not r['start_ms']<=t*1000<=r['end_ms']:return False
    cuts=facts.get('tracking',{}).get('camera_cuts',{}).get(camera)
    if cuts is None:return False
    # Fixed geometry never carries across a detected camera cut.
    return bisect.bisect_right(sorted(cuts),r['reference_ms']/1000)==bisect.bisect_right(sorted(cuts),t)

def context(p,d,facts):
    if p.get('occluded') or p.get('box_source')=='optical_flow':return None
    if p.get('identity_method') not in {'direct_vote_track','yolo_botsort_ocr','human_reviewed_track'}:return None
    camera=p.get('camera');box=p.get('box',[])
    if len(box)!=4:return None
    foot=[box[0]+box[2]/2,box[1]+box[3]]
    alliance=(facts.get('bumpers',{}).get('identities',{}).get(str(p['team'])) or {}).get('alliance')
    applicable=[r for r in d['regions'] if active(r,p['t'],camera,facts) and r['alliance'] in ('neutral',alliance)]
    zones=[{'id':r['id'],'kind':r['kind'],'label':r.get('label',''),'alliance':r['alliance']} for r in applicable if r['kind']!='scoring_target' and inside(foot,r['points'])]
    targets=[]
    for r in applicable:
        if r['kind']!='scoring_target':continue
        centre=[sum(q[i] for q in r['points'])/len(r['points']) for i in (0,1)]
        targets.append({'id':r['id'],'alliance':r['alliance'],'normalized_distance':round(math.dist(foot,centre),5)})
    return {'version':VERSION,'camera':camera,'position_basis':'estimated_box_bottom_center','zones':zones,'targets':targets,'scoring_proven':False}

def enrich(tags,facts,game_key,root=None):
    d=load(facts,game_key,root)
    if not d:return list(tags),{'status':'no_matching_source_annotations','version':VERSION}
    sightings={}
    for p in facts.get('tracking',{}).get('localizations',[]):sightings.setdefault(p['team'],[]).append(p)
    result=[];matched=0
    for tag in tags:
        row=dict(tag);t=tag['start_ms']/1000
        candidates=[p for p in sightings.get(tag['team'],[]) if abs(p['t']-t)<=.3]
        evidence=[(abs(p['t']-t),context(p,d,facts)) for p in candidates]
        evidence=[(dt,c) for dt,c in evidence if c and (c['zones'] or c['targets'])]
        if evidence:
            row['field_context']=min(evidence,key=lambda v:v[0])[1];matched+=1
        result.append(row)
    return result,{'status':'applied_as_supporting_context','version':VERSION,'regions':len(d['regions']),'tags_with_context':matched,'source_sha256':d['source_sha256'],'limitation':'Fixed camera geometry; does not establish scoring or change model probabilities.'}

def observations(facts,game_key,root=None):
    d=load(facts,game_key,root)
    if not d:return {'status':'no_matching_source_annotations','robots':[]}
    robots={}
    seen=set()
    for p in facts.get('tracking',{}).get('localizations',[]):
        c=context(p,d,facts)
        if not c:continue
        row=robots.setdefault(p['team'],{'team':p['team'],'zone_observations':{}})
        for z in c['zones']:
            key=(p['team'],z['id'],round(p['t'],3))
            if key in seen:continue
            seen.add(key);row['zone_observations'][z['kind']]=row['zone_observations'].get(z['kind'],0)+1
    return {'status':'observed_context_only','source_sha256':d['source_sha256'],'regions':len(d['regions']),'robots':list(robots.values()),'scoring_proven':False}

def sync(config,video,facts):
    """Fetch this owner's saved geometry through the existing helper bearer auth."""
    import urllib.request
    from neptune_helper import public_https,NoRedirect
    sha=facts['source']['sha256'];video=Path(video)
    try:
        # A missing connection or video is "unavailable", like a network failure; never fatal.
        url=public_https(config['site'].rstrip('/')+'/api/field-regions.php')
        request=urllib.request.Request(url,data=json.dumps({'video_name':video.name,'video_size':video.stat().st_size,'source_sha256':sha}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+config['token']})
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=20) as response:
            raw=response.read(2097153)
        if len(raw)>2097152:raise ValueError('Region document too large')
        document=json.loads(raw).get('document')
        if document is None:return {'status':'no_cloud_annotations'}
        d=validate(document)
        if d['source']['name']!=video.name or d['source']['size']!=video.stat().st_size or d.get('source_sha256',sha)!=sha:raise ValueError('Region source mismatch')
        d=dict(d,source_sha256=sha,binding_method='verified_local_video_and_authenticated_owner_export')
        # User-owned data goes outside the signed app bundle.
        folder=Path.home()/'.neptune-trainer/field-regions';folder.mkdir(parents=True,exist_ok=True)
        target=folder/(sha+'.json');temp=target.with_suffix('.pending');temp.write_text(json.dumps(d,allow_nan=False));temp.replace(target)
        return {'status':'synced','regions':len(d['regions'])}
    except Exception as error:
        return {'status':'cloud_sync_unavailable','error_type':type(error).__name__}
