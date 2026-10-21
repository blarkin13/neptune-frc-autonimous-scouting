#!/usr/bin/env python3
"""Standalone Apple Silicon app. Pinned runtimes; no private models or credentials."""
import argparse,hashlib,json,os,plistlib,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'macos/NeptuneTrainingHelper';BUILD=ROOT/'.helper-build/native';DEPS=BUILD/'deps'
PUB='0c89Plhfoix3bOGZt9qtq5jrM8Y5K7w9ysSmcsSb+rY='
def run(*args):subprocess.run([str(a) for a in args],check=True)
def clone(source,target):
    if target.exists():shutil.rmtree(target) if target.is_dir() else target.unlink()
    target.parent.mkdir(parents=True,exist_ok=True);run('/bin/cp','-cR',source,target)
def main():
    p=argparse.ArgumentParser();p.add_argument('--version',default='3.0.4');p.add_argument('--build',default='30006');p.add_argument('--feed',default='https://neptunefrc.com/community/downloads/mac/appcast.xml');p.add_argument('--local-update-test',action='store_true');p.add_argument('--reuse-site-packages',type=Path);p.add_argument('--archive',action='store_true');args=p.parse_args()
    if not args.local_update_test and not args.feed.startswith('https://'):p.error('Release feeds must use HTTPS.')
    out=BUILD/('test' if args.local_update_test else 'release')/args.build;app=out/'Neptune Training Helper.app';contents=app/'Contents';res=contents/'Resources';exe=contents/'MacOS';frameworks=contents/'Frameworks';out.mkdir(parents=True,exist_ok=True)
    if app.exists():shutil.rmtree(app)
    for d in (res,exe,frameworks):d.mkdir(parents=True,exist_ok=True)
    clone(DEPS/'runtime/python',res/'python');site=res/'python/lib/python3.13/site-packages'
    if args.reuse_site_packages:
        clone(args.reuse_site_packages,site)
    else:run(res/'python/bin/python3.13','-m','pip','install','--no-cache-dir','-r',SRC/'requirements-lock.txt')
    # Verify the reused environment really matches the complete pinned package set.
    actual=json.loads(subprocess.check_output([str(res/'python/bin/python3.13'),'-I','-m','pip','list','--format=json']))
    normal=lambda x:x.lower().replace('_','-')
    found={normal(r['name']):r['version'] for r in actual}
    for row in (SRC/'requirements-lock.txt').read_text().splitlines():
        if row.strip() and not row.startswith('#'):
            name,version=row.split('==');assert found.get(normal(name))==version,(name,found.get(normal(name)),version)
    # Remove mutable bytecode and pip tools, never include host-specific venv launchers.
    for d in list(site.rglob('__pycache__')):shutil.rmtree(d)
    engine=res/'engine';engine.mkdir();
    for source in (ROOT/'helper').iterdir():
        if source.is_file() and ((source.suffix=='.py' and not source.name.startswith('test_')) or source.name in ('requirements.json','requirements-yolo.txt','requirements-videomae.txt','season_rules.json')):shutil.copy2(source,engine/source.name)
    for name in ('native_worker.py','native_connect.py','native_bootstrap.py'):shutil.copy2(SRC/name,engine/name)
    if not (ROOT/'helper/bin/neptune-ocr').exists():run('/bin/sh',ROOT/'helper/vision/build.sh')
    clone(ROOT/'helper/bin',engine/'bin')
    vendor=engine/'vendor/bin';vendor.mkdir(parents=True)
    for name in ('ffmpeg','ffprobe'):shutil.copy2(BUILD/'ffmpeg-build/ffmpeg-9.0.2'/name,vendor/name)
    qjs=BUILD/'quickjs-2026-06-04/qjs'
    if not qjs.exists():
        run('/usr/bin/tar','-xf',ROOT/'.helper-build/vendor/quickjs-2026-06-04.tar.xz','-C',BUILD)
        subprocess.run(['make','-j4','qjs'],cwd=qjs.parent,env=dict(os.environ,MACOSX_DEPLOYMENT_TARGET='14.0'),check=True)
    shutil.copy2(qjs,vendor/'qjs')
    filters=subprocess.check_output([str(vendor/'ffmpeg'),'-hide_banner','-filters'],text=True)
    for required in ('fps','crop','scale','split','format'):assert any(line.split()[1:2]==[required] for line in filters.splitlines()),'Missing video filter '+required
    protocols=subprocess.check_output([str(vendor/'ffmpeg'),'-hide_banner','-protocols'],text=True);assert 'pipe' in protocols
    clone(DEPS/'sparkle/Sparkle.framework',frameworks/'Sparkle.framework')
    for name in ('Logo-transparent.png',):
        if (SRC/'Resources'/name).exists():shutil.copy2(SRC/'Resources'/name,res/name)
    icon=SRC/'Resources/Icon.png'
    if icon.exists():
        iconset=BUILD/'Neptune.iconset';iconset.mkdir(exist_ok=True)
        for size in (16,32,128,256,512):
            for scale in (1,2):run('/usr/bin/sips','-z',size*scale,size*scale,icon,'--out',iconset/('icon_%sx%s%s.png'%(size,size,'@2x' if scale==2 else '')))
        run('/usr/bin/iconutil','-c','icns',iconset,'-o',res/'Neptune.icns')
    info={'CFBundleIdentifier':'com.neptunefrc.traininghelper','CFBundleName':'Neptune Training Helper','CFBundleDisplayName':'Neptune Training Helper','CFBundleExecutable':'NeptuneTrainingHelper','CFBundlePackageType':'APPL','CFBundleShortVersionString':args.version,'CFBundleVersion':args.build,'LSMinimumSystemVersion':'14.0','LSApplicationCategoryType':'public.app-category.developer-tools','CFBundleIconFile':'Neptune','NSHighResolutionCapable':True,'SUFeedURL':args.feed,'SUPublicEDKey':PUB,'SUEnableAutomaticChecks':True,'SUAutomaticallyUpdate':False,'SUScheduledCheckInterval':21600,'SUVerifyUpdateBeforeExtraction':True,'SURequireSignedFeed':True,'SUEnableInstallerLauncherService':True,'SUEnableDownloaderService':True,'NSHumanReadableCopyright':'Neptune Training Helper. Third-party licenses in Resources/Licenses.'}
    if args.local_update_test:info['NSAppTransportSecurity']={'NSAllowsLocalNetworking':True}
    (contents/'Info.plist').write_bytes(plistlib.dumps(info));(contents/'PkgInfo').write_text('APPL????')
    licenses=res/'Licenses';licenses.mkdir();shutil.copy2(DEPS/'sparkle/LICENSE',licenses/'Sparkle.txt')
    shutil.copy2(ROOT/'.helper-build/vendor/quickjs-2026-06-04/LICENSE',licenses/'QuickJS-MIT.txt')
    shutil.copy2(BUILD/'ffmpeg-build/ffmpeg-9.0.2/COPYING.LGPLv2.1',licenses/'FFmpeg-LGPL.txt')
    corresponding=res/'CorrespondingSource';corresponding.mkdir();shutil.copy2(ROOT/'.helper-build/vendor/ffmpeg-9.0.2.tar.xz',corresponding/'ffmpeg-9.0.2.tar.xz');shutil.copy2(ROOT/'scripts/build-native-ffmpeg.sh',corresponding/'build-native-ffmpeg.sh')
    (licenses/'Dependencies.txt').write_text('Python package license files are included in python/lib/python3.13/site-packages/*.dist-info/licenses.\nVideo tools use the existing Neptune prerequisite distribution; see engine/requirements.json.\n')
    shutil.copy2(SRC/'requirements-lock.txt',res/'requirements-lock.txt')
    (res/'engine-identity.json').write_text(subprocess.check_output([sys.executable,'-c',"import sys,json;sys.path.insert(0,'helper');import neptune_engine;print(json.dumps(neptune_engine.identity()))"],cwd=ROOT).decode())
    run('/usr/bin/swiftc','-module-cache-path',BUILD/'module-cache','-O','-parse-as-library','-target','arm64-apple-macos14.0','-F',frameworks,'-framework','Sparkle','-framework','AppKit','-framework','Security','-Xlinker','-rpath','-Xlinker','@executable_path/../Frameworks',SRC/'App.swift','-o',exe/'NeptuneTrainingHelper')
    # Sparkle ships signed nested code. Leave those signatures intact; ad-hoc sign our executable/bundle.
    identity=os.environ.get('NEPTUNE_CODESIGN_IDENTITY','-')
    if identity!='-':
        magic={bytes.fromhex(x) for x in ('cffaedfe','feedfacf','cafebabe','bebafeca','cefaedfe')}
        for binary in sorted(app.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if binary.is_file() and not binary.is_symlink():
                with binary.open('rb') as f:kind=f.read(4)
                if kind in magic:run('/usr/bin/codesign','--force','--sign',identity,'--options','runtime','--timestamp',binary)
        for bundle in sorted(app.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if bundle.is_dir() and bundle.suffix in ('.app','.xpc','.framework'):run('/usr/bin/codesign','--force','--sign',identity,'--options','runtime','--timestamp',bundle)
    signing=['/usr/bin/codesign','--force','--sign',identity]
    if identity!='-':signing+=['--options','runtime','--timestamp']
    run(*signing,app);run('/usr/bin/codesign','--verify','--deep','--strict',app)
    if args.archive:run('/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',app,out/('Neptune-Training-Helper-'+args.version+'.zip'))
    print(app)
if __name__=='__main__':main()
