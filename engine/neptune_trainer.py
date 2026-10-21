"""Owner-connected desktop trainer. GPU fits the current baseline; video/OCR remains separate."""
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

HOME=Path.home()/'.neptune-trainer'

class TrainingApiError(ValueError):
    def __init__(self,message,status):
        super().__init__(message);self.status=status


def connection_error(error):
    if isinstance(error,TrainingApiError):return error.status in (408,429,500,502,503,504)
    if isinstance(error,urllib.error.HTTPError):return error.code in (408,429,500,502,503,504)
    if isinstance(error,(TimeoutError,ConnectionError)):return True
    if isinstance(error,urllib.error.URLError):
        import ssl
        return not isinstance(error.reason,ssl.SSLCertVerificationError)
    return False


def api(config,action,payload):
    # Claim/start requests are not replayed blindly: a timed-out response may already
    # have reserved work. Heartbeats and existing lease-bound result writes are safe.
    repeatable=action in {'status','heartbeat','page_heartbeat','trial_heartbeat','finish','pause','trial_finish','page_evaluation_finish','page_fail'}
    for attempt in range(3 if repeatable else 1):
        try:return _api_once(config,action,payload)
        except Exception as error:
            if not repeatable or not connection_error(error) or attempt==2:raise
            time.sleep(1+attempt*2)


def _api_once(config,action,payload):
    from neptune_helper import public_https,NoRedirect
    url=public_https(config['site'].rstrip('/')+'/api/community-training.php?action='+action)
    request=urllib.request.Request(url,data=json.dumps(payload,allow_nan=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+config['token']})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=60) as response:
            raw=response.read(32*1024**2+1)
            if len(raw)>32*1024**2:raise ValueError('Training snapshot exceeds this client’s 32 MB limit.')
            return json.loads(raw)
    except urllib.error.HTTPError as error:
        try:message=json.loads(error.read(4096)).get('error')
        except (ValueError,AttributeError):message=None
        raise TrainingApiError(message or 'Neptune rejected the training request (%s).'%error.code,error.code) from None

def setup_device(choice,progress):
    device={'Mac GPU':'mps','NVIDIA GPU':'cuda','CPU':'cpu'}.get(choice)
    if not device:
        device='mps' if sys.platform=='darwin' and platform.machine()=='arm64' else 'cuda' if shutil.which('nvidia-smi') else 'cpu'
    if device=='cpu':return {'platform':platform.system(),'device':'cpu','name':'CPU (no GPU fitting selected)'}
    try:import numpy
    except ImportError:
        progress('Installing the numeric library required by GPU training…')
        subprocess.run([sys.executable,'-m','pip','install','numpy>=1.26,<3'],check=True)
    try:import torch
    except ImportError:
        progress('Installing the GPU training library. This is a large one-time download…')
        command=[sys.executable,'-m','pip','install','torch==2.9.1']
        if device=='cuda':command+=['--index-url','https://download.pytorch.org/whl/cu128']
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in process.stdout:progress(line.strip()[:300])
        if process.wait()!=0:raise ValueError('GPU library installation failed. Check free space and the setup messages, then retry. CPU mode is also available.')
        import importlib;importlib.invalidate_caches();import torch
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('NVIDIA GPU unavailable. Install a compatible NVIDIA driver or explicitly choose CPU. See pytorch.org/get-started/locally/.')
    if device=='mps' and not torch.backends.mps.is_available():raise ValueError('Apple GPU unavailable. This training mode needs a supported Apple Silicon Mac; choose CPU otherwise.')
    # Confirm allocation and execution, not merely a reported device name.
    x=torch.ones((8,8),device=device);float((x@x).sum().cpu())
    return {'platform':platform.system(),'device':device,'name':torch.cuda.get_device_name(0) if device=='cuda' else 'Apple GPU (Metal)','torch_version':torch.__version__}

def run_job(config,job,hardware,progress,benchmark=None,max_matches=None,should_pause=None,transport=None):
    from neptune_training import run,evaluate_benchmark,activate
    import neptune_games as games
    call=transport or api
    root=HOME/'jobs'/job['id'];root.mkdir(parents=True,exist_ok=True)
    snapshot=job['snapshot'].encode()
    if hashlib.sha256(snapshot).hexdigest()!=job['snapshot_sha256']:raise ValueError('Training snapshot fingerprint mismatch.')
    prior_snapshot=root/'labels.ndjson'
    recovered=root/'result.json'
    # A finish rejection does not erase the fitted model. Retry the saved result
    # under the fresh reservation, without repeating downloads, OCR or fitting.
    if recovered.is_file() and prior_snapshot.is_file() and hashlib.sha256(prior_snapshot.read_bytes()).hexdigest()==job['snapshot_sha256'] and not (root/'receipt.json').exists():
        output=json.loads(recovered.read_text());progress('Recovering the saved model result — no video processing is needed.')
        reply=call(config,'finish',{'job_id':job['id'],'lease':job['lease'],'result':output})
        (root/'receipt.json').write_text(json.dumps(reply));
        if (root/'job-state.json').exists():(root/'job-state.json').unlink()
        return reply
    prior_snapshot.write_bytes(snapshot)
    state_file=root/'job-state.json'
    state_file.write_text(json.dumps({'id':job['id'],'site':config['site'],'state':'running'}));state_file.chmod(0o600)
    pack=dict(job['game_pack'],season=job['season']);pack_file=root/'game.json';pack_file.write_text(json.dumps(pack));games.install(pack_file,root)
    state={'message':'Preparing training','checkpoint':None,'stop_requested':False};done=threading.Event();lost=[]
    def send_heartbeat():
        payload={'job_id':job['id'],'lease':job['lease'],'message':state['message']}
        if state['checkpoint'] is not None:payload['checkpoint']=state['checkpoint']
        reply=call(config,'page_heartbeat' if job.get('control') else 'heartbeat',payload)
        state['stop_requested']=bool(reply.get('stop_requested'))
        return reply
    def heartbeat():
        while not done.wait(5 if job.get('control') else 20):
            try:send_heartbeat()
            except Exception as error:lost.append(error);return
    def status(message):
        if lost:raise lost[0]
        state['message']=str(message)[:900];progress(message)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        os.environ['NEPTUNE_TRAIN_DEVICE']=hardware['device']
        os.environ['NEPTUNE_GAMES_HOME']=str(root)
        site_key=hashlib.sha256(config['site'].rstrip('/').encode()).hexdigest()[:24]
        def checkpoint(info):
            state['checkpoint']=info;status('%d of %d matches prepared · %s'%(info['matches_done'],info['matches_total'],info['current_match'] or info['phase']))
            if job.get('control'):send_heartbeat()
        result=run(root/'training',job['season'],export_path=root/'labels.ndjson',progress=status,
                   cache_root=HOME/'cache'/site_key,max_matches=max_matches,should_pause=lambda:state['stop_requested'] or bool(should_pause and should_pause()),checkpoint=checkpoint)
        if result.get('state')=='paused':
            # End heartbeat activity before changing the server job to paused.
            done.set();thread.join(timeout=65)
            if lost:raise lost[0]
            reply=call(config,'pause',{'job_id':job['id'],'lease':job['lease'],'matches_done':result['matches_done'],'matches_total':result['matches_total'],**({'message':result['message']} if result.get('message') else {})})
            state_file.write_text(json.dumps({'id':job['id'],'site':config['site'],'state':'paused'}))
            return dict(reply,matches_done=result['matches_done'],matches_total=result['matches_total'])
        folder=Path(result['folder']);model=json.loads((folder/'model.json').read_text());evaluated=None
        if benchmark and (model['heads'] or model.get('scoring_head')):
            evaluated=evaluate_benchmark(root/'training',folder,Path(benchmark),status)
            if evaluated.get('release_ready'):activate(root/'training',folder);model=json.loads((folder/'model.json').read_text())
        result['training_computer']=hardware
        output={'report':result,'model':model,'benchmark':evaluated}
        pending=root/'result.json';pending.write_text(json.dumps(output,allow_nan=False))
        if lost:raise lost[0]
        reply=call(config,'finish',{'job_id':job['id'],'lease':job['lease'],'result':output})
        (root/'receipt.json').write_text(json.dumps(reply));
        if (root/'job-state.json').exists():(root/'job-state.json').unlink()
        return reply
    finally:done.set();thread.join(timeout=2)

def watch_jobs(config,hardware,execute,progress,closing,pause,busy=lambda value:None,connection=lambda value:None,failed=lambda message:None,device_changed=lambda:False):
    """Keep transport interruptions separate from rejected jobs and credentials."""
    pending=None;connected=False
    while not closing.is_set():
        if not pending and device_changed():return
        try:
            if pending:
                api(config,'page_heartbeat',{'job_id':pending['id'],'lease':pending['lease'],'message':'Reconnected; recovering saved match work'})
                job=pending
            else:
                job=api(config,'page_claim',{'hardware':hardware}).get('job')
                if job:pause.clear()
            if not connected:connection(True);connected=True
            if not job:
                busy(False);progress('Ready. Choose training or a match test on Neptune.')
                closing.wait(5);continue
            busy(True);pending=job
            reply=execute(config,job,hardware,progress,stop=pause.is_set)
            pending=None
            progress('Paused safely. Resume on Neptune.' if reply.get('state') in ('remote_paused','server_paused') else 'Finished. Results are saved on Neptune.')
            busy(False)
        except Exception as error:
            if connection_error(error):
                connected=False;connection(False)
                progress('Connection interrupted — reconnecting automatically. Saved match work is kept. Keep this helper open.')
                closing.wait(5);continue
            if pending:
                try:api(config,'page_fail',{'job_id':pending['id'],'lease':pending['lease'],'message':str(error)[:900]})
                except Exception:pass
                pending=None
            busy(False);failed(str(error))
            if isinstance(error,TrainingApiError) and error.status in (401,403):return
            closing.wait(5)


def result_message(state):
    return {
        'needs_data': 'Finished — no candidate could be fitted. Your report is saved on Neptune; check it for video or robot-localization gaps. Your tags are kept.',
        'remote_paused': 'Paused after the current match. Progress is saved. Choose Run 1 match or Continue to resume.',
        'candidate': 'Finished — a model candidate is saved on Neptune. It needs evaluation before release.',
    }.get(state, 'Finished — your report is saved on Neptune.')


def main():
    """The helper supplies compute; Neptune's web page owns every run control."""
    import tkinter as tk
    from tkinter import ttk,messagebox
    import webbrowser
    from neptune_setup import LocalSetup,configure_tools
    from neptune_page_worker import execute
    os.environ['NEPTUNE_HELPER_PIPELINE']='facts';configure_tools()
    source=Path(__file__).with_name('trainer-connection.json')
    if not source.is_file():raise ValueError('Download the connected training helper from Neptune.')
    config=json.loads(source.read_text());HOME.mkdir(mode=0o700,exist_ok=True)
    root=tk.Tk();root.title('Neptune Training Helper');root.geometry('790x560');root.minsize(620,470)
    frame=ttk.Frame(root,padding=28);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Neptune Training Helper',font=('',23,'bold')).pack(anchor='w')
    from neptune_engine import VERSION as engine_version
    ttk.Label(frame,text='Engine '+engine_version+' · Neptune controls training and match tests'+(' · Connection '+config['computer_id'][:4].upper() if config.get('computer_id') else ''),wraplength=710).pack(anchor='w',pady=(5,22))
    status=tk.StringVar(value='Connecting to Neptune…');ttk.Label(frame,textvariable=status,font=('',14,'bold'),wraplength=710).pack(anchor='w',fill='x',pady=10)
    ttk.Label(frame,text='Leave this window open. Return to Neptune to choose matches, run training, watch progress and see the results.',wraplength=710).pack(anchor='w',pady=10)
    ttk.Button(frame,text='Open Neptune training page',command=lambda:webbrowser.open(config['site'].rstrip('/')+'/admin/community-learning.php?connect=1')).pack(anchor='w',pady=12)
    choice=tk.StringVar(value='Automatic');settings=ttk.Frame(frame);settings.pack(fill='x',pady=5)
    ttk.Label(settings,text='Training device').pack(side='left',padx=(0,10));device=ttk.Combobox(settings,textvariable=choice,values=['Automatic','Mac GPU','NVIDIA GPU','CPU'],state='readonly',width=20);device.pack(side='left')
    log=tk.Text(frame,height=8,wrap='word',state='disabled');log.pack(fill='both',expand=True,pady=12)
    messages=queue.Queue();closing=threading.Event();pause=threading.Event();busy={'value':False};reviewing=threading.Event();review_closing=threading.Event()
    def progress(text):messages.put(('progress',str(text)))
    def stop_current():pause.set();progress('Finishing this match, then pausing. Progress stays saved on Neptune.')
    stop_button=ttk.Button(frame,text='Stop after this match',command=stop_current,state='disabled');stop_button.pack(anchor='w')
    def review_tracking():
        if busy['value']:messagebox.showinfo('Training is running','Finish or pause training before opening a tracking review.');return
        if reviewing.is_set():review_closing.set();return
        reviewing.set();review_closing.clear();review_button.config(text='Close tracking review')
        def review_worker():
            try:
                from neptune_identity_review import choose
                choose(HOME/'jobs',HOME/'identity-reviews',review_closing,webbrowser.open)
            except Exception as error:progress('Tracking review: '+str(error))
            finally:reviewing.clear();messages.put(('review_closed',None))
        threading.Thread(target=review_worker,daemon=True).start()
    review_button=ttk.Button(frame,text='Review robot tracking…',command=review_tracking);review_button.pack(anchor='w',pady=5)
    def worker():
        hardware=None;selected=None
        while not closing.is_set():
            if reviewing.is_set():closing.wait(.5);continue
            try:
                api(config,'status',{'hardware':{'training_protocol':'page-setup-v1','name':'Preparing this computer','platform':platform.system()}})
                progress('Connected. Checking video tools…');LocalSetup().install(lambda text:progress('Video tools and text reader ready.' if str(text).startswith('This computer is ready') else text))
                if hardware is None or selected!=choice_value['value']:
                    selected=choice_value['value'];hardware=setup_device(selected,progress)
                from neptune_yolo import prepare_runtime, fingerprint
                prepare_runtime(progress, hardware['device'])
                from neptune_training import prepare_action_encoder
                hardware['action_features']=prepare_action_encoder(progress)
                hardware['robot_detector_sha256']=fingerprint();hardware['robot_tracking']='yolo-botsort-1'
                os.environ['NEPTUNE_TRACKING_DEVICE']='0' if hardware['device']=='cuda' else hardware['device']
                from neptune_engine import identity
                engine=identity();hardware['engine_version']=engine['version'];hardware['engine_sha256']=engine['sha256']
                hardware['label_contracts']=['game-builder-moments-v1'];hardware['training_protocol']='page-v2';hardware['outside_adapters']=['viper-2026-activity-v1','mapped-actions-v1','viper-2026-points-v1'];progress('Connected — ready. Choose what to run on Neptune.')
                watch_jobs(config,hardware,execute,progress,closing,pause,
                    busy=lambda value:messages.put(('busy',value)),
                    failed=lambda message:progress('Needs attention: '+message),
                    device_changed=lambda:selected!=choice_value['value'] or reviewing.is_set())
            except Exception as error:
                progress('Connection needs attention: '+str(error)+' Open Neptune to check the connection. Your saved files are kept.')
                if closing.wait(15):break
        messages.put(('closed',None))
    choice_value={'value':choice.get()}
    def poll():
        choice_value['value']=choice.get()
        while not messages.empty():
            kind,message=messages.get()
            if kind=='closed':review_closing.set();root.destroy();return
            if kind=='review_closed':review_button.config(text='Review robot tracking…');continue
            if kind=='busy':busy['value']=message;review_button.config(state='disabled' if message else 'normal');stop_button.config(state='normal' if message else 'disabled');device.config(state='disabled' if message else 'readonly');continue
            status.set(message);log.config(state='normal');log.insert('end',time.strftime('%H:%M:%S')+'  '+message+'\n')
            if int(log.index('end-1c').split('.')[0])>250:log.delete('1.0','2.0')
            log.see('end');log.config(state='disabled')
        root.after(250,poll)
    def close():
        if busy['value'] and not messagebox.askyesno('Finish this match and close?','Finish the current match, save progress and close the helper?'):return
        closing.set()
        if busy['value']:pause.set();status.set('Finishing this match, saving progress, then closing…')
    root.protocol('WM_DELETE_WINDOW',close);threading.Thread(target=worker,daemon=True).start();poll();root.mainloop()


if __name__=='__main__':main()
