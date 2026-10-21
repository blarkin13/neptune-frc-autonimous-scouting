import json, glob, sys, collections, numpy as np
C='/Users/brianlarkin/.neptune-trainer'
files=[glob.glob(C+'/cache/7c3b85dfdb685839b584aeb4/prepared/*/'+p+'*.json')[0] for p in ('d962757b64','4777fbd0f0','70c55a2326','89557faa31')]
labels={}
for l in open(C+'/jobs/9df8015cdc6ca57fbe77fa746816e153/labels.ndjson'):
    r=json.loads(l); labels[r['id']]=r
roster={}
for r in labels.values():
    if r.get('roster'): roster[r['match_key']]=r['roster']
rows=[]; clips={}
for f in files:
    d=json.load(open(f))
    for e in d['examples']:
        x=d['features'][e['feature']]; c=e.get('temporal_clip')
        rows.append(dict(e,x=x))
        if c: clips[e['feature']]=(e,c,x)
print('rows',len(rows),'unique clips',len(clips))
X=np.array([v[2] for v in clips.values()]); meta=[(v[0],v[1]) for v in clips.values()]
var=X.var(0); print('R3D per-dim variance quantiles 10/50/90:',np.round(np.quantile(var,[.1,.5,.9]),4),' dims with var<0.01:',int((var<.01).sum()),'of',X.shape[1], ' mean value',round(float(X.mean()),3))
def auc(s,y):
    s=np.asarray(s);y=np.asarray(y);P=s[y==1][:,None];N=s[y==0][None,:]
    return float(((P>N).sum()+.5*(P==N).sum())/(P.size*N.size)) if P.size and N.size else None
def logreg(Xtr,ytr,l2=1.0,it=300):
    mu=Xtr.mean(0);sd=Xtr.std(0)+1e-6;Z=(Xtr-mu)/sd;w=np.zeros(Z.shape[1]);b=0.
    sw=np.where(ytr==1,(ytr==0).sum()/max(1,(ytr==1).sum()),1.)
    for _ in range(it):
        p=1/(1+np.exp(-(Z@w+b)));g=(p-ytr)*sw;w-=.1*(Z.T@g/len(ytr)+l2*w/len(ytr));b-=.1*g.mean()
    return lambda Xt:((Xt-mu)/sd)@w+b
groups=np.array([m[0]['source_sha256'] for m in meta])
def grouped_auc(y,name):
    y=np.array(y);s=np.zeros(len(y));ok=np.zeros(len(y),bool)
    for g in np.unique(groups):
        tr=groups!=g;te=~tr
        if len(np.unique(y[tr]))<2:continue
        s[te]=logreg(X[tr],y[tr])(X[te]);ok[te]=True
    print('  probe %-34s held-out-match AUC %.3f  (n=%d, positives=%d)'%(name,auc(s[ok],y[ok]),ok.sum(),int(y[ok].sum())))
cam=[1 if 'closeup' in str(c['scene']) else 0 for e,c in meta]
phase=[1 if c['phase']=='auto' else 0 for e,c in meta]
red=[1 if e['team'] in roster[e['match_key']]['red'] else 0 for e,c in meta]
def disp(c):
    f=c['frames'];a=f[0]['box'];b=f[-1]['box']
    return abs((a[0]+a[2]/2)-(b[0]+b[2]/2))+abs((a[1]+a[3]/2)-(b[1]+b[3]/2))
dd=np.array([disp(c) for e,c in meta]); moving=list((dd>np.quantile(dd,.66)).astype(int)); still=dd<np.quantile(dd,.33)
mv=[1 if m else 0 for m in moving]
print('Sanity probes on frozen R3D clip embeddings (labels derived from tracker metadata, not humans):')
grouped_auc(cam,'close-up vs wide camera')
grouped_auc(red,'red vs blue bumper')
grouped_auc(phase,'autonomous vs teleop')
keep=(dd>np.quantile(dd,.66))|still
y=np.array(mv);
s=np.zeros(len(y));ok=np.zeros(len(y),bool)
for g in np.unique(groups):
    tr=(groups!=g)&keep;te=(groups==g)&keep
    if len(np.unique(y[tr]))<2 or not te.any():continue
    s[te]=logreg(X[tr],y[tr])(X[te]);ok[te]=True
print('  probe %-34s held-out-match AUC %.3f  (n=%d)'%('moving (top third) vs still (bottom third)',auc(s[ok],y[ok]),ok.sum()))
np.save(sys.argv[1] if len(sys.argv)>1 else '/dev/null',X) if False else None
