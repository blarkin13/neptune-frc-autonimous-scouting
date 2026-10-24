"""JSON-lines bridge. Credentials arrive over a pipe, never process arguments/files."""
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

WIRE=sys.stdout
LOCK=threading.Lock()
def emit(event, **values):
    with LOCK:
        WIRE.write(json.dumps(dict(event=event,**values),allow_nan=False)+'\n');WIRE.flush()

def main():
    commands=queue.Queue();pause=threading.Event();closing=threading.Event()
    def reader():
        for line in sys.stdin:
            try: command=json.loads(line)
            except ValueError:continue
            if command.get('command') in ('stop','quit'):pause.set()
            if command.get('command')=='quit':closing.set()
            commands.put(command)
        closing.set();pause.set()
    threading.Thread(target=reader,daemon=True).start()
    command=commands.get();config=command.get('connection');device=command.get('device','Automatic')
    if command.get('command')=='connect':
        from native_connect import connect
        result=connect(command.get('site','https://neptunefrc.com'),lambda s:emit('status',message=s),closing)
        emit('credential',connection=result);return
    if command.get('command')=='review':
        from neptune_identity_review import choose
        tools=Path(__file__).parent/'vendor/bin';os.environ['PATH']=str(tools)+':/usr/bin:/bin:/usr/sbin:/sbin'
        os.environ['NEPTUNE_ROBOT_MODELS']=str(Path.home()/'Library/Application Support/Neptune Training Helper/robot-models')
        import neptune_setup
        neptune_setup.video_js_runtime=lambda:{'quickjs':{'path':str(tools/'qjs')}}
        choose(Path.home()/'.neptune-trainer/jobs',Path.home()/'.neptune-trainer/identity-reviews',closing,lambda url:emit('review_url',url=url),connection=config)
        return
    if not config:raise ValueError('Connect your Neptune account first.')
    import neptune_trainer as trainer
    import neptune_setup
    from neptune_setup import LocalSetup
    import subprocess
    tools=Path(__file__).parent/'vendor/bin'
    def bundled_tools():
        os.environ['PATH']=str(tools)+':/usr/bin:/bin:/usr/sbin:/sbin'
        return {name:tools/name for name in ('ffmpeg','ffprobe')}
    def bundled_js():
        try:subprocess.run([str(tools/'qjs'),'--eval','if (1 + 1 !== 2) throw new Error("runtime check failed")'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        except (OSError,subprocess.SubprocessError) as error:raise ValueError('The included video runtime could not start. Quit and reopen the helper; if macOS shows a security prompt, approve the Neptune app in Privacy & Security.') from error
        return {'quickjs':{'path':str(tools/'qjs')}}
    neptune_setup.configure_tools=bundled_tools
    neptune_setup.video_js_runtime=bundled_js
    from neptune_engine import identity
    from neptune_page_worker import execute
    os.environ['NEPTUNE_HELPER_PIPELINE']='facts'
    last_message=[None]
    def progress(message):
        if message!=last_message[0]:emit('status',message=str(message));last_message[0]=message
    trainer.api(config,'status',{'hardware':{'training_protocol':'page-setup-v1','name':'Neptune Training Helper','platform':'Darwin'}})
    emit('connection',connected=True)
    if command.get('command')=='verify':
        LocalSetup().install(progress);emit('verified',engine=identity()['version']);return
    LocalSetup().install(progress)
    hardware=trainer.setup_device(device,progress)
    models=Path(os.environ['NEPTUNE_ROBOT_MODELS']);manifest=models/'manifest.json'
    if not manifest.exists():
        progress('Downloading authorized robot recognition tools…')
        result=trainer.api(config,'runtime_bundle',{})
        rows=result.get('files',[])
        if not rows:raise ValueError('Neptune has not enabled native-app robot tools. Install the reviewed server update or import your existing helper tools.')
        expected={'manifest.json','best_bumper_model.pt','coco_model.pt'}
        if set(r.get('name') for r in rows)!=expected:raise ValueError('Invalid robot tools response.')
        models.mkdir(parents=True,exist_ok=True,mode=0o700)
        for row in sorted(rows,key=lambda r:r['name']=='manifest.json'):
            data=base64.b64decode(row['data'],validate=True)
            if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Robot tools verification failed.')
            path=models/row['name'];temp=path.with_suffix('.pending');temp.write_bytes(data);temp.chmod(0o600);temp.replace(path)
    from neptune_yolo import prepare_runtime,fingerprint
    from neptune_training import prepare_action_encoder
    prepare_runtime(progress,hardware['device']);VERSION=prepare_action_encoder(progress)
    try:
        import neptune_selfcheck,neptune_robot_jobs
        neptune_robot_jobs.api(config,'selfcheck_put',neptune_selfcheck.run(progress))
    except Exception as error:progress('Self-check could not finish: '+str(error)[:200])
    hardware.update(label_contracts=['game-builder-moments-v1'],action_features=VERSION,robot_detector_sha256=fingerprint(),robot_tracking='yolo-botsort-1',engine_version=identity()['version'],engine_sha256=identity()['sha256'],training_protocol='page-v2',outside_adapters=['viper-2026-activity-v1','mapped-actions-v1','viper-2026-points-v1'])
    os.environ['NEPTUNE_TRACKING_DEVICE']='0' if hardware['device']=='cuda' else hardware['device']
    os.environ['NEPTUNE_TRAIN_DEVICE']=hardware['device']   # clip features in match tests too, not only in training
    trainer.watch_jobs(config,hardware,execute,progress,closing,pause,
        busy=lambda value:emit('busy',value=value),
        connection=lambda value:emit('connection',connected=value),
        failed=lambda message:emit('error',message=message))

if __name__=='__main__':
    # Libraries/tool subprocesses may write stdout; keep the protocol channel separate.
    with contextlib.redirect_stdout(sys.stderr):
        try:main()
        except Exception as error:emit('error',message=str(error));sys.exit(1)
