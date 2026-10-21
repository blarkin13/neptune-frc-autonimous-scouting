import json, glob, sys, collections, random, numpy as np
sys.path.insert(0,'/private/tmp/claude-501/-Users-brianlarkin-Documents-ChatGPT-Neptune-neptune-frc-scouting/379c750c-d470-4314-86c9-a7e3552f7169/scratchpad/work/engine')
import os; os.environ['NEPTUNE_TRAIN_DEVICE']='cpu'
import neptune_training as T
C='/Users/brianlarkin/.neptune-trainer'
files=[glob.glob(C+'/cache/7c3b85dfdb685839b584aeb4/prepared/*/'+p+'*.json')[0] for p in ('d962757b64','4777fbd0f0','70c55a2326','89557faa31')]
labels={json.loads(l)['id']:json.loads(l) for l in open(C+'/jobs/9df8015cdc6ca57fbe77fa746816e153/labels.ndjson')}
roster={r['match_key']:r['roster'] for r in labels.values() if r.get('roster')}
rows=[]
for f in files:
    d=json.load(open(f))
    for e in d['examples']: rows.append(dict(e,x=d['features'][e['feature']]))
def meta(r):
    c=r.get('temporal_clip') or {}
    return ('closeup' if 'closeup' in str(c.get('scene')) else 'wide', 'red' if r['team'] in roster[r['match_key']]['red'] else 'blue', c.get('phase'))
for tag in ('scoring','gb:score_1_fuel','gb:score_2_fuel'):
    rs=[r for r in rows if r['tag']==tag]
    P=[meta(r) for r in rs if r['y']==1]; U=[meta(r) for r in rs if r['y'] is None]
    f=lambda L,i,v: round(sum(m[i]==v for m in L)/max(1,len(L)),2)
    print(tag,'P',len(P),'U',len(U),'| close-up share P/U',f(P,0,'closeup'),f(U,0,'closeup'),'| red share P/U',f(P,1,'red'),f(U,1,'red'),'| sources P',len({r['source_sha256'] for r in rs if r['y']==1}),'| teams P',dict(collections.Counter(r['team'] for r in rs if r['y']==1)))
# exact replication of production validation for generic scoring
rs=[r for r in rows if r['tag']=='scoring']
detail,rate=T.validate_positive_unlabeled(rs)
print('replicated production validation:',detail['auc_vs_unlabeled'],detail['status'],'folds',detail['folds'])
# out-of-fold scores to bootstrap by source
positives=collections.defaultdict(list)
for r in rs:
    if r['y']==1: positives[r['source_sha256']].append(r)
sources=sorted(positives);count=min(5,len(sources))
fold_of={s:i%count for i,s in enumerate(sorted(sources,key=T.digest))}
for s in sorted({r['source_sha256'] for r in rs}-set(sources)):fold_of[s]=int(T.digest(s)[:8],16)%count
oof=[]
for fold in range(count):
    head=T.fit_positive_unlabeled([r for r in rs if fold_of[r['source_sha256']]!=fold])
    for r in rs:
        if fold_of[r['source_sha256']]==fold and r['y']!=0: oof.append((r['source_sha256'],T.score(head,r['x']),r['y']==1, meta(r)))
def auc(items):
    p=[s for _,s,y,_ in items if y];u=[s for _,s,y,_ in items if not y]
    return T.pu_auc(p,u)
print('oof AUC',round(auc(oof),4))
rng=random.Random(1);srcs=sorted({o[0] for o in oof});boot=[]
for _ in range(2000):
    pick=[rng.choice(srcs) for _ in srcs];items=[o for s in pick for o in oof if o[0]==s]
    a=auc(items)
    if a is not None:boot.append(a)
boot.sort();print('source-cluster bootstrap 95% interval',round(boot[int(.025*len(boot))],3),round(boot[int(.975*len(boot))],3),'over',len(srcs),'source videos')
# metadata-only head: does R3D beat camera+alliance+phase indicators?
def metax(r):
    m=meta(r);return [1.0 if m[0]=='closeup' else 0.0,1.0 if m[1]=='red' else 0.0,1.0 if m[2]=='auto' else 0.0]
mrs=[dict(r,x=metax(r)) for r in rs]
d2,_=T.validate_positive_unlabeled(mrs);print('same validation, features = camera+alliance+phase only:',d2['auc_vs_unlabeled'])
