"""Server side of a helper release, run on the Neptune host through AWS SSM with /tmp/neptune-release-manifest.json.

Fetches the commit tarball and release assets, checks every SHA-256 and that live server files still match the last
deployed commit, backs up what it replaces, installs code, downloads and the apt repo, publishes the update feeds last,
rolls back on failure, then prunes old releases. The manifest lists commit, backup, code, before, mac/windows/linux assets.
"""
import hashlib,json,os,shutil,subprocess,tarfile,urllib.request,time
from pathlib import Path
M=json.loads(Path('/tmp/neptune-release-manifest.json').read_text())
root=Path('/var/www/neptune');web=root/'public_html/Neptune';eng=root/'neptune_secure/community-learning';dl=web/'community/downloads'
stage=Path('/tmp/neptune-release-stage');shutil.rmtree(stage,ignore_errors=True);stage.mkdir()
backup=Path(M['backup']);backup.mkdir(mode=0o700,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def get(url,dst):
    for a in range(4):
        try:
            with urllib.request.urlopen(url,timeout=600) as r,open(dst,'wb') as f:shutil.copyfileobj(r,f,1<<20)
            return
        except Exception:
            if a==3:raise
            time.sleep(5)
# 1. Fetch and verify everything before touching the site.
get('https://codeload.github.com/blarkin13/neptune-frc-autonimous-scouting/tar.gz/'+M['commit'],stage/'src.tgz')
with tarfile.open(stage/'src.tgz') as t:
    top=t.getnames()[0].split('/')[0]
    for rel in M['code']:t.extract(top+'/'+rel,stage,filter='data')
src=stage/top
for rel,h in M['code'].items():assert sha(src/rel)==h,rel
for rel,h in M['before'].items():assert sha(root/rel[len('server/'):])==h,('live file differs from the last deployed commit',rel)
files={}
for group in ('mac','windows','linux'):
    for name,(url,h) in M[group].items():
        p=stage/group/name;p.parent.mkdir(exist_ok=True);get(url,p);assert sha(p)==h,(group,name);files[group,name]=p
for rel in M['code']:
    if rel.endswith('.php'):subprocess.run(['php','-l',str(src/rel)],check=True,capture_output=True)
    if rel.endswith('.py'):compile((src/rel).read_text(),rel,'exec')
print('fetched and verified',len(M['code'])+sum(len(M[g]) for g in ('mac','windows','linux')),'files',flush=True)
changed=[]
def install(srcp,dst,owner=(33,33),mode=0o644):
    dst=Path(dst);existed=dst.exists()
    if existed:
        b=backup/dst.relative_to(root);b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,b)
    changed.append((dst,existed));dst.parent.mkdir(parents=True,exist_ok=True)
    tmp=dst.with_name(dst.name+'.release-tmp');shutil.copyfile(srcp,tmp);os.chown(tmp,*owner);tmp.chmod(mode);os.replace(tmp,dst)
def text(t,dst):
    p=stage/('text-'+Path(dst).name);p.write_text(t);install(p,dst)
def allow(folder,name):
    h=folder/'.htaccess';t=h.read_text() if h.exists() else 'Options -Indexes\n'
    if '"'+name+'"' not in t:text(t+'\n<Files "'+name+'">\n Require all granted\n</Files>\n',h)
def sums(folder,fname,names):
    s=folder/fname;lines=s.read_text().splitlines() if s.exists() else []
    lines=[l for l in lines if not any(l.endswith('  '+n) for n in names)]+[sha(folder/n)+'  '+n for n in names];text('\n'.join(lines)+'\n',s)
mac,win,lin=dl/'mac',dl/'windows',dl/'linux';macz=M['mac_zip'];winz=M['win_zip'];linz=M['lin_zip']
apt_swapped=False
try:
    for rel in M['code']:
        if rel.startswith('server/'):install(src/rel,root/rel[len('server/'):])
        elif rel.startswith('engine/'):install(src/rel,eng/rel[len('engine/'):])
    install(files['mac',macz],mac/macz);allow(mac,macz)
    install(files['mac','Neptune-Training-Helper.dmg'],mac/'Neptune-Training-Helper.dmg',owner=(0,33))
    install(files['windows',winz],win/winz);allow(win,winz)
    install(files['windows','Neptune-Training-Helper-Setup.exe'],win/'Neptune-Training-Helper-Setup.exe')
    install(files['linux','Neptune-Training-Helper_all.deb'],lin/'Neptune-Training-Helper_all.deb',owner=(0,33))
    install(files['linux',linz],lin/linz);allow(lin,linz)
    new=web/'apt.new';shutil.rmtree(new,ignore_errors=True);new.mkdir()
    with tarfile.open(files['linux','apt-repo.tar.gz']) as t:t.extractall(new,filter='data')
    if (web/'apt/.htaccess').is_file():shutil.copy2(web/'apt/.htaccess',new/'.htaccess')
    subprocess.run(['chown','-R','www-data:www-data',str(new)],check=True);assert (new/'dists').is_dir() and (new/'neptune.gpg').is_file()
    if (web/'apt.old').exists():shutil.move(str(web/'apt.old'),str(backup/'apt.old-leftover'))
    shutil.copytree(web/'apt',backup/'apt');os.rename(web/'apt',web/'apt.old');os.rename(new,web/'apt');apt_swapped=True;shutil.rmtree(web/'apt.old')
    # Update feeds last, after every file they point to is in place.
    install(files['windows','latest.json'],win/'latest.json');install(files['linux','latest.json'],lin/'latest.json');install(files['mac','appcast.xml'],mac/'appcast.xml')
    sums(lin,'SHA256SUMS.txt',['Neptune-Training-Helper_all.deb',linz,'latest.json'])
    sums(mac,'SHA256SUMS',[macz,'appcast.xml']);sums(win,'SHA256SUMS',[winz,'latest.json'])
    receipt={'commit':M['commit'],'changed':len(changed),'backup':str(backup),'engine':[l for l in (eng/'neptune_engine.py').read_text().splitlines() if l.startswith('VERSION')][0]}
    (backup/'receipt.json').write_text(json.dumps(receipt,indent=1));print(json.dumps(receipt),flush=True)
except Exception:
    for dst,existed in reversed(changed):
        if existed:shutil.copy2(backup/dst.relative_to(root),dst)
        elif dst.exists():dst.unlink()
    if apt_swapped:
        shutil.rmtree(web/'apt',ignore_errors=True);shutil.copytree(backup/'apt',web/'apt');subprocess.run(['chown','-R','www-data:www-data',str(web/'apt')])
    raise
finally:
    shutil.rmtree(stage,ignore_errors=True)
# Old zips and backups (AGENTS.md rule 10).
print(subprocess.run(['/usr/local/sbin/neptune-prune-releases'],capture_output=True,text=True).stdout[-1500:],flush=True)
