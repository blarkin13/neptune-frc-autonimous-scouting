#!/usr/bin/env python3
"""Build a Mac update from the installed runtime and this repo's canonical engine."""
import argparse,hashlib,json,plistlib,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/'engine'
sys.path.insert(0,str(ENGINE))
import neptune_engine

def run(*args):subprocess.run([str(a) for a in args],check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-app',type=Path,default=Path('/Applications/Neptune Training Helper.app'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--sparkle-bin',type=Path,required=True)
    args=parser.parse_args()
    version='3.2.7';build='30208';out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    app=out/'Neptune Training Helper.app'
    if app.exists():raise ValueError('Release app already exists; choose a new empty output directory')
    run('/bin/cp','-cR',args.base_app,app)
    res=app/'Contents/Resources';dest=res/'engine'
    for name in neptune_engine.FILES:shutil.copy2(ENGINE/name,dest/name)
    shutil.copy2(ROOT/'trainer-app/macos/NeptuneTrainingHelper/native_worker.py',dest/'native_worker.py')
    (res/'engine-identity.json').write_text(json.dumps(neptune_engine.identity()))
    info=app/'Contents/Info.plist';document=plistlib.loads(info.read_bytes());document.update(CFBundleShortVersionString=version,CFBundleVersion=build);info.write_bytes(plistlib.dumps(document))
    exe=app/'Contents/MacOS/NeptuneTrainingHelper';frameworks=app/'Contents/Frameworks'
    run('/usr/bin/swiftc','-module-cache-path',out/'swift-module-cache','-O','-parse-as-library','-target','arm64-apple-macos14.0','-F',frameworks,'-framework','Sparkle','-framework','AppKit','-framework','Security','-Xlinker','-rpath','-Xlinker','@executable_path/../Frameworks',ROOT/'trainer-app/macos/NeptuneTrainingHelper/App.swift','-o',exe)
    run('/usr/bin/codesign','--force','--sign','-',app)
    run('/usr/bin/codesign','--verify','--deep','--strict',app)
    archive=out/f'Neptune-Training-Helper-{version}.zip'
    run('/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive)
    feed=out/'public-release';feed.mkdir()
    shutil.copy2(archive,feed/archive.name)
    run(args.sparkle_bin/'generate_appcast','--account','neptune-training-helper','--download-url-prefix','https://neptunefrc.com/community/downloads/mac/','--maximum-deltas','0',feed)
    # Build an installer for fresh downloads from the same signed app.
    stage=out/'dmg-stage';stage.mkdir();run('/bin/cp','-cR',app,stage/app.name);(stage/'Applications').symlink_to('/Applications')
    (stage/'Read Me.txt').write_text('Drag Neptune Training Helper into Applications and open it there. Saved reviews on this Mac remain in ~/.neptune-trainer.\n')
    dmg=feed/'Neptune-Training-Helper.dmg'
    run('/usr/bin/hdiutil','create','-volname','Neptune Training Helper','-srcfolder',stage,'-format','UDZO','-ov',dmg)
    shutil.rmtree(stage)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (feed/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(feed.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'))
    print(json.dumps({'version':version,'build':build,'engine':neptune_engine.identity()['version'],'archive':str(archive),'dmg':str(dmg),'feed':str(feed)}))

if __name__=='__main__':main()
