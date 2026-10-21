"""Offline, two-direction identity reconciliation. Suggestions are never training truth.

The forward/backward dynamic program considers every assignment of the three
alliance roster entries to the visible detections. Later anchors can resolve
past ambiguity. Independent camera shots/cuts and long gaps never share state.
Only existing verified anchors and explicit human corrections are trusted.
"""
import collections,hashlib,itertools,json,math
VERSION='bidirectional-roster-review-v4'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def roster_check(roster):
    if not isinstance(roster,dict) or set(roster)!={'red','blue'} or any(len(roster[c])!=3 for c in roster):raise ValueError('A verified three-red/three-blue roster is required')
    values=[n for c in ('red','blue') for n in roster[c]]
    if any(type(n)!=int or n<=0 for n in values) or len(set(values))!=6:raise ValueError('Roster entries must be six distinct team numbers')

def motion(a,b,dt,association=None):
    ax,ay,aw,ah=a['box'];bx,by,bw,bh=b['box']
    distance=math.hypot(ax+aw/2-bx-bw/2,ay+ah/2-by-bh/2)
    scale=max(.015,aw,bw)
    # A tracker ID is a small association hint, never an identity anchor.
    base=min(30.,(distance/max(scale,4*scale*dt))**2)+(0.12 if a['track_id']!=b['track_id'] else 0.)
    if association is not None:
        from neptune_review_learning import pair_features,probability
        x=pair_features(a,b)
        if x is not None:base+=min(4.,-math.log(max(.01,probability(association,x))))
    return base

def transition(a,sa,b,sb,association=None):
    previous={team:p for team,p in zip(sa,a)};current={team:p for team,p in zip(sb,b)}
    # Penalize an unexplained disappearance/reappearance. Otherwise a single
    # continuously visible box can change team for zero cost between anchors.
    return 2.*len(previous.keys()^current.keys())+sum(motion(previous[t],current[t],b[0]['t']-a[0]['t'],association) for t in previous.keys()&current.keys())

def solve_window(frames,teams,margin,association=None):
    states=[];costs=[]
    for frame in frames:
        options=list(itertools.permutations(teams,len(frame)))
        trusted=[p.get('verified_team') for p in frame]
        valid=[s for s in options if all(v is None or s[i]==v for i,v in enumerate(trusted))]
        if not valid:  # Contradictory verified anchors must not be chosen by convenience.
            return [dict(p,team=None,identity_status='unknown',reason='conflicting_verified_anchors') for f in frames for p in f]
        states.append(valid)
        costs.append([sum(6. if p.get('read_teams') and t not in p['read_teams'] else 0. for p,t in zip(frame,s)) for s in valid])
    forward=[costs[0][:]];edges=[]
    for k in range(1,len(frames)):
        edge=[[transition(frames[k-1],a,frames[k],b,association) for b in states[k]] for a in states[k-1]];edges.append(edge)
        forward.append([costs[k][j]+min(forward[k-1][i]+edge[i][j] for i in range(len(states[k-1]))) for j in range(len(states[k]))])
    backward=[[0.]*len(s) for s in states]
    for k in range(len(frames)-2,-1,-1):
        backward[k]=[min(edges[k][i][j]+costs[k+1][j]+backward[k+1][j] for j in range(len(states[k+1]))) for i in range(len(states[k]))]
    anchors=collections.defaultdict(list)
    for frame in frames:
        for p in frame:
            if p.get('verified_team') is not None:anchors[(p['camera'],str(p['scene']),p['track_id'])].append(p)
    optimum=min(forward[-1]);out=[]
    for k,frame in enumerate(frames):
        totals=[a+b for a,b in zip(forward[k],backward[k])]
        for i,p in enumerate(frame):
            scores={team:min((v for s,v in zip(states[k],totals) if s[i]==team),default=math.inf) for team in teams}
            plausible=[team for team,v in scores.items() if v<=optimum+margin]
            team=plausible[0] if len(plausible)==1 else None
            trusted=p.get('verified_team')
            def overlaps(q):
                x,y,w,h=p['box'];a,b,c,d=q['box']
                return max(0,min(x+w,a+c)-max(x,a))*max(0,min(y+h,b+d)-max(y,b))/max(1e-9,min(w*h,c*d))>.2
            contact=trusted is None and len(states[k])>1 and any(q is not p and overlaps(q) for q in frame)
            contact_supported=False
            if contact and team is not None:
                known=anchors[(p['camera'],str(p['scene']),p['track_id'])]
                before=next((q for q in reversed(known) if 0<p['t']-q['t']<=1.5),None)
                after=next((q for q in known if 0<q['t']-p['t']<=1.5),None)
                contact_supported=before is not None and after is not None and before['verified_team']==after['verified_team']==team and motion(before,p,p['t']-before['t'])<4 and motion(p,after,after['t']-p['t'])<4
            if contact and not contact_supported:team=None
            status='verified' if trusted is not None else 'inferred' if team is not None else 'unknown'
            out.append(dict(p,team=team,identity_status=status,reason='verified_ocr_segment' if trusted is not None else 'same_number_before_and_after_contact' if contact_supported else 'bidirectional_motion_and_roster' if team is not None else 'same_alliance_overlap_needs_review' if contact else 'multiple_roster_assignments',
                candidate_teams=plausible,identity_evidence={'solver':VERSION,'uses_future_evidence':True,'training_eligible':trusted is not None}))
    return out

def reconcile(observations,roster,source_sha256,margin=1.0,association=None):
    roster_check(roster)
    if not isinstance(source_sha256,str) or len(source_sha256)!=64:raise ValueError('Video fingerprint required')
    if not 0<=margin<=10:raise ValueError('Invalid ambiguity margin')
    groups=collections.defaultdict(lambda:collections.defaultdict(list));out=[]
    for raw in observations:
        p=dict(raw)
        if p.get('alliance') not in roster or type(p.get('t')) not in (int,float) or not math.isfinite(p['t']) or p['t']<0:raise ValueError('Invalid tracking observation')
        box=p.get('box')
        if not isinstance(box,list) or len(box)!=4 or not all(type(x) in (int,float) and math.isfinite(x) for x in box) or box[2]<=0 or box[3]<=0 or min(box)<0 or box[0]+box[2]>1.001 or box[1]+box[3]>1.001:raise ValueError('Invalid normalized box')
        if p.get('verified_team') is not None and p['verified_team'] not in roster[p['alliance']]:raise ValueError('Anchor not in alliance roster')
        p['point_id']=digest([source_sha256,p['camera'],p['scene'],p['t'],p['track_id'],box])
        groups[(p['camera'],str(p['scene']),p['alliance'])][p['t']].append(p)
    for _,timeline in sorted(groups.items()):
        window=[];last=None
        def flush():
            if window:out.extend(solve_window(window,roster[window[0][0]['alliance']],margin,association));window.clear()
        for t,frame in sorted(timeline.items()):
            ids=[p['track_id'] for p in frame]
            ambiguous=len(frame)>3 or len(set(ids))!=len(ids)
            if ambiguous or last is not None and t-last>1.5:flush()
            if ambiguous:
                out.extend(dict(p,team=None,identity_status='unknown',reason='too_many_or_duplicate_detections',candidate_teams=roster[p['alliance']]) for p in frame)
            else:window.append(sorted(frame,key=lambda p:str(p['track_id'])))
            last=t
        flush()
    out.sort(key=lambda p:(p['t'],p['camera'],str(p['scene']),str(p['track_id'])))
    # Split display/correction tracks at gaps; a recycled numeric track ID is not a single robot.
    tracks=collections.defaultdict(list)
    for p in out:tracks[(p['camera'],str(p['scene']),p['alliance'],p['track_id'])].append(p)
    for key,points in tracks.items():
        serial=0;last=None
        for p in points:
            if last is not None and p['t']-last>1.5:serial+=1
            p['review_track']=digest([source_sha256,key,serial])[:24];last=p['t']
    return {'schema_version':1,'solver':VERSION,'source_sha256':source_sha256,'roster':roster,'points':out,'corrections':[],
        'summary':dict(collections.Counter(p['identity_status'] for p in out)),'limitations':['Inferred identities are review suggestions, not training labels.','No identity is carried across camera cuts or long unseen gaps.','Roster elimination requires distinct visible detections; false detections still need human review.']}

def apply_corrections(review,corrections):
    """Human anchors rerun both directions; original automatic evidence stays untouched."""
    roster_check(review['roster'])
    if not isinstance(corrections,list) or len(corrections)>1000:raise ValueError('Invalid correction list')
    original={p['point_id']:p for p in review['points']};points=[dict(p) for p in review['points']];manual={}
    for edit in corrections:
        if set(edit) not in ({'review_track','start','end','team'},{'review_track','start','end','team','ignored'}) or type(edit['start']) not in (int,float) or type(edit['end']) not in (int,float) or not all(math.isfinite(edit[k]) for k in ('start','end')) or not 0<=edit['start']<=edit['end']:raise ValueError('Invalid correction interval')
        if 'ignored' in edit and type(edit['ignored'])!=bool:raise ValueError('Invalid exclusion')
        selected=[p for p in points if p['review_track']==edit['review_track'] and edit['start']<=p['t']<=edit['end']]
        if not selected:raise ValueError('Correction does not match a visible track interval')
        team=edit['team']
        if edit.get('ignored') and team is not None:raise ValueError('Excluded boxes cannot carry an identity')
        if team is not None and (type(team)!=int or any(team not in review['roster'][p['alliance']] for p in selected)):raise ValueError('Correction team is not in this alliance')
        for p in selected:manual[p['point_id']]={'team':team,'ignored':edit.get('ignored',False)}
    frames=collections.defaultdict(dict)
    for p in points:
        m=manual.get(p['point_id'])
        if m and m['team'] is not None:
            key=(p['camera'],str(p['scene']),p['t'])
            if m['team'] in frames[key]:raise ValueError('Two boxes cannot be assigned the same robot in one camera frame')
            frames[key][m['team']]=p['point_id']
    usable=[];excluded=[]
    for p in points:
        m=manual.get(p['point_id']);key=(p['camera'],str(p['scene']),p['t'])
        if m and m['ignored']:
            excluded.append(dict(p,team=None,identity_status='excluded',reason='human_not_robot'));continue
        if m:p['verified_team']=m['team'];p['read_teams']=[]
        # A human correction overrides conflicting automatic identity evidence.
        if p.get('verified_team') in frames[key] and frames[key][p['verified_team']]!=p['point_id']:p['verified_team']=None;p['read_teams']=[]
        usable.append(p)
    refined=reconcile(usable,review['roster'],review['source_sha256'])['points'] if usable else []
    for p in refined:
        p['review_track']=original[p['point_id']]['review_track']
        m=manual.get(p['point_id'])
        if m:p.update(team=m['team'],identity_status='corrected' if m['team'] is not None else 'unknown',reason='human_correction',identity_evidence={'training_eligible':False,'human_identity_review':True})
        # Do not promote propagation from a human anchor to independently verified OCR.
        elif p['identity_status']=='verified' and original[p['point_id']].get('verified_team') is None:p['identity_status']='inferred'
    combined=sorted(refined+excluded,key=lambda p:(p['t'],p['camera'],str(p['scene']),str(p['track_id'])))
    return {**review,'points':combined,'corrections':corrections,'summary':dict(collections.Counter(p['identity_status'] for p in combined))}
