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
    repeatable=action in {'status','heartbeat','page_heartbeat','trial_heartbeat','finish','pause','trial_finish','page_evaluation_finish','page_fail','review_list','review_get','review_put'}
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

def engine_version():
    try:
        from neptune_engine import VERSION
        return 'engine '+VERSION
    except Exception:return ''

def helper_version():
    """The installed helper's version (Windows and Linux builds ship build-version.json next to this file)."""
    try:return json.loads(Path(__file__).with_name('build-version.json').read_text())['version']
    except (OSError,ValueError,KeyError):return ''

def setup_ocr_gpu(progress):
    """Swap the CPU onnxruntime for the CUDA 13 build so number reading runs on the NVIDIA card. A failure leaves reading on the CPU."""
    # Read the package list, not the module: importing onnxruntime here would lock its files on Windows.
    from importlib.metadata import version,PackageNotFoundError
    try:version('onnxruntime-gpu');return
    except PackageNotFoundError:pass
    try:version('onnxruntime')
    except PackageNotFoundError:return
    progress('Installing GPU number reading (one-time download)…')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    pip=[sys.executable,'-m','pip']
    try:
        subprocess.run(pip+['uninstall','-y','onnxruntime'],check=True,capture_output=True,**flags)
        process=subprocess.Popen(pip+['install','onnxruntime-gpu[cuda,cudnn]==1.31.0'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,**flags)
        for line in process.stdout:progress(line.strip()[:300])
        if process.wait()!=0:raise OSError('pip failed')
    except (OSError,subprocess.SubprocessError) as error:
        progress('GPU number reading could not be installed (%s); reading stays on the CPU.'%str(error)[:120])
        subprocess.run(pip+['install','onnxruntime==1.31.0'],capture_output=True,**flags)

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
        # torchvision must come from the same build as torch (a CPU torchvision with CUDA torch fails on import).
        command=[sys.executable,'-m','pip','install','torch==2.9.1','torchvision==0.24.1']
        if device=='cuda':command+=['--index-url','https://download.pytorch.org/whl/cu128']
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in process.stdout:progress(line.strip()[:300])
        if process.wait()!=0:raise ValueError('GPU library installation failed. Check free space and the setup messages, then retry. CPU mode is also available.')
        import importlib;importlib.invalidate_caches();import torch
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('NVIDIA GPU unavailable. Install a compatible NVIDIA driver or explicitly choose CPU. See pytorch.org/get-started/locally/.')
    if device=='mps' and not torch.backends.mps.is_available():raise ValueError('Apple GPU unavailable. This training mode needs a supported Apple Silicon Mac; choose CPU otherwise.')
    if device=='cuda':setup_ocr_gpu(progress)
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
    from neptune_steps import Steps
    steps=Steps('actions') if benchmark is None else None
    def status(message):
        if lost:raise lost[0]
        message=steps.describe(message) if steps else message
        state['message']=str(message)[:900];progress(message)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        os.environ['NEPTUNE_TRAIN_DEVICE']=hardware['device']
        os.environ['NEPTUNE_GAMES_HOME']=str(root)
        site_key=hashlib.sha256(config['site'].rstrip('/').encode()).hexdigest()[:24]
        def checkpoint(info):
            state['checkpoint']=info;status('%d of %d matches prepared · %s'%(info['matches_done'],info['matches_total'],info['current_match'] or info['phase']))
            if job.get('control'):send_heartbeat()
        try:
            # Saved scoring areas for each event in this batch: training applies them to every match there.
            from neptune_field_regions import sync_events,event_key
            events={event_key(json.loads(line).get('match_key')) for line in (root/'labels.ndjson').read_text().splitlines() if line.strip()}
            sync_events(config,events)
        except (OSError,ValueError):pass
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
    pending=None;connected=False;last_cleanup=None
    # Keep awake (set on Neptune → My computers) follows whether a job is running.
    from neptune_awake import shared
    awake=shared();show_busy=busy;show_progress=progress;last_message=['']
    import neptune_telemetry as telemetry
    def busy(value):
        awake.set_busy(value);show_busy(value)
        if not value:telemetry.clear()
    def progress(message):
        last_message[0]=str(message);show_progress(message)
        telemetry.note(str(message).split('\n')[-1] if 'Now:' not in str(message) else next((l[4:].strip() for l in str(message).split('\n') if l.startswith('Now:')),str(message)))
    # Check in for My computers and the Running now console every 5 s while working (15 s idle), from its own thread.
    import neptune_robot_jobs as robot_jobs
    if not getattr(telemetry,'reporter',None):telemetry.reporter=telemetry.Reporter(lambda payload:robot_jobs.api(config,'computer_poll',payload,timeout=20),
                       lambda:{'busy':awake.busy,'awake':awake.active,'message':last_message[0][:600],'version':helper_version() or engine_version(),'platform':'%s · %s'%(platform.system().replace('Darwin','Mac'),hardware.get('name','CPU'))},
                       lambda reply:awake.set_mode((reply.get('settings') or {}).get('keep_awake','jobs')),closing).start()
    def housekeeping(force=False):
        # Startup, after every job, and hourly while idle: remove only re-downloadable media.
        nonlocal last_cleanup
        if not force and last_cleanup is not None and time.monotonic()-last_cleanup<3600:return
        from neptune_housekeeping import sweep
        try:sweep(HOME,progress=progress)
        except (OSError,ValueError):pass
        last_cleanup=time.monotonic()
    housekeeping(force=True)
    last_detector=[0.,0.,False]   # detector sync time, detector poll time, score-moments backfill done
    def detector_work():
        # Robot-detector requests from Auto Scout -> Robot labels, and the shared detector, while idle.
        import neptune_robot_jobs as robot_jobs
        now=time.monotonic()
        if now-last_detector[0]>3600:
            for sync in (robot_jobs.sync_detector,robot_jobs.sync_field_detector):
                try:sync(config)
                except Exception:pass
            last_detector[0]=now
        if now-last_detector[1]>30:
            last_detector[1]=now
            try:robot_jobs.run_pending(config,progress,busy)
            except Exception:pass
            # Scoreboard score changes for Watch & tag (a tagging aid, never a training input).
            try:
                import neptune_score_moments as moments
                if not last_detector[2]:moments.backfill();last_detector[2]=True
                moments.send_pending(config,robot_jobs.api)
            except Exception:pass
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
                housekeeping()
                detector_work()
                busy(False);progress('Ready. Choose training or a match test on Neptune.')
                closing.wait(5);continue
            busy(True);pending=job
            reply=execute(config,job,hardware,progress,stop=pause.is_set)
            pending=None
            housekeeping(force=True)
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


def start_reconnect_process(source, executable=None):
    """Hand a stopped helper to the installed owner-approval entry point."""
    source=Path(source)
    entry=source.with_name('neptune_trainer_entry.py')
    if not entry.is_file():raise FileNotFoundError('The installed reconnect entry point is missing. Reinstall the helper.')
    return subprocess.Popen([executable or sys.executable,str(entry),'--reconnect'],cwd=str(source.parent),close_fds=True)


def main():
    """The helper supplies compute; Neptune's web page owns every run control."""
    import tkinter as tk
    from tkinter import ttk,messagebox
    import webbrowser
    from neptune_setup import LocalSetup,configure_tools
    from neptune_page_worker import execute
    import neptune_ui as ui
    os.environ['NEPTUNE_HELPER_PIPELINE']='facts';configure_tools()
    source=Path(__file__).with_name('trainer-connection.json')
    if not source.is_file():raise ValueError('Download the connected training helper from Neptune.')
    config=json.loads(source.read_text());HOME.mkdir(mode=0o700,exist_ok=True)
    root=tk.Tk();root.title('Neptune Training Helper '+helper_version());root.geometry('1000x760');root.minsize(640,460)
    ui.apply(root)
    if sys.platform == 'win32':
        try:root.iconbitmap(str(source.with_name('Neptune.ico')))
        except tk.TclError:pass
    # One resizable window: this computer's card and controls, then Neptune's readouts, then activity.
    emblem,wide=Path(__file__).with_name('neptune-logo-square.png'),Path(__file__).with_name('neptune-logo-wide.png')
    _bar,top_status,bar_buttons=ui.topbar(root,logo=emblem)
    holder=tk.Frame(root,bg=ui.INK);holder.pack(fill='both',expand=True)
    page=frame=ui.BubblePage(holder)
    from neptune_engine import VERSION as engine_version
    page.add(ui.wordmark(page,wide))
    computer_card=ui.ComputerCard(page,name=platform.node() or 'Training computer',logo=emblem);computer_card.pack_forget();page.add(computer_card)
    status=tk.StringVar(value='Connecting to Neptune…');job_title=tk.StringVar(value='THIS COMPUTER');next_value=tk.StringVar(value='')
    job_outer=tk.Frame(page,bg=ui.LINE,padx=1,pady=1,height=62);job_outer.pack_propagate(False);page.add(job_outer)
    job=tk.Frame(job_outer,bg=ui.PANEL,padx=12,pady=10);job.pack(fill='both',expand=True)
    tk.Label(job,textvariable=job_title,font=('Arial',9,'bold'),fg=ui.ACCENT,bg=ui.PANEL,anchor='w').pack(fill='x')
    status_label=tk.Label(job,textvariable=status,font=('Arial',10),fg=ui.TEXT,bg=ui.PANEL,anchor='nw',justify='left',height=1,wraplength=900);status_label.pack(fill='x',pady=(5,0))
    stage_value=tk.DoubleVar(value=0);stage_text=tk.StringVar(value='Waiting for stage counters')
    stage_box=tk.Frame(job,bg=ui.PANEL)
    tk.Label(stage_box,textvariable=stage_text,font=('Courier',9),fg=ui.MUTED,bg=ui.PANEL).pack(anchor='w')
    ttk.Progressbar(stage_box,variable=stage_value,maximum=100,style='Meter.Horizontal.TProgressbar').pack(fill='x')
    progress_box=tk.Frame(job,bg=ui.PANEL);progress_value=tk.DoubleVar(value=0);remaining=tk.StringVar(value='No assigned job')
    tk.Label(progress_box,textvariable=remaining,font=('Courier',9),fg=ui.MUTED,bg=ui.PANEL).pack(anchor='w')
    ttk.Progressbar(progress_box,variable=progress_value,maximum=100,style='Neptune.Horizontal.TProgressbar').pack(fill='x')
    next_label=tk.Label(job,textvariable=next_value,font=('Arial',9),fg=ui.MUTED,bg=ui.PANEL,anchor='w')
    def show_progress(text):
        lines=text.split('\n');line=next((x for x in lines if x.startswith('Progress: ')),None)
        if line:
            rest=line[len('Progress: '):];digits=''.join(ch for ch in rest.split('%')[0] if ch.isdigit())
            if digits:progress_value.set(float(digits));remaining.set(rest)
        job_title.set(lines[0] if any(x.startswith('Now:') for x in lines) else 'THIS COMPUTER')
        next_value.set(next((x for x in lines if x.startswith('Next:')),''))
        if text.startswith('Ready.') or text.startswith('Connected — ready.'):return 'No assigned job'
        return next((x for x in lines if x.startswith('Now:')),text)
    controls=bar_buttons
    ttk.Button(controls,text='Open Neptune',style='Neptune.TButton',command=lambda:webbrowser.open(config['site'].rstrip('/')+'/autoscout/train.php?connect=1')).pack(side='right',padx=(8,0))
    choice=tk.StringVar(value='Automatic');settings=ttk.Frame(page,style='Neptune.TFrame');page.add(settings)
    ttk.Label(settings,text='Training device',style='Muted.TLabel').pack(side='left',padx=(0,12))
    devices=['Automatic','NVIDIA GPU','CPU'] if sys.platform in ('win32','linux') else ['Automatic','Mac GPU','CPU']
    device=ttk.Combobox(settings,textvariable=choice,values=devices,state='readonly',width=18,style='Neptune.TCombobox');device.pack(side='left')
    # Neptune's readouts go between this computer's rows and the bottom rows; see the 'dashboard' message.
    toggle_row=ttk.Frame(page,style='Neptune.TFrame');page.add(toggle_row)
    # The activity log stays hidden until asked for.
    activity_box=tk.Frame(page,bg=ui.INK,height=1);activity_inner=ttk.Frame(activity_box,style='Neptune.TFrame');log=ui.activity(activity_inner);page.add(activity_box)
    actions=ttk.Frame(page,style='Neptune.TFrame');page.add(actions)
    bottom=[toggle_row,activity_box,actions];pinned=set(widget for widget,_ in page.items)
    def resize_helper():page.after_idle(page.relayout)
    def toggle_activity():
        if activity_inner.winfo_ismapped():
            activity_inner.pack_forget();activity_box.configure(height=1);activity_button.config(text='Show activity')
        else:
            activity_inner.pack(fill='both',expand=True);activity_button.config(text='Hide activity')
        resize_helper()
    ttk.Label(toggle_row,text='v'+helper_version()+' · Engine '+engine_version.split('-')[0],style='Muted.TLabel').pack(side='right')
    activity_button=ttk.Button(toggle_row,text='Show activity',style='Subtle.TButton',command=toggle_activity);activity_button.pack(side='left')
    messages=queue.Queue();closing=threading.Event();pause=threading.Event();busy={'value':False};reviewing=threading.Event();review_closing=threading.Event()
    import neptune_telemetry as telemetry
    unsubscribe_meters=telemetry.subscribe(lambda payload:messages.put(('telemetry',payload)))
    reconnect_requested={'value':False}
    def reconnect():
        if reconnect_requested['value']:return
        if busy['value'] and not messagebox.askyesno('Reconnect after this match?','Finish the current match and save progress before reconnecting this computer to Neptune?'):return
        reconnect_requested['value']=True
        reconnect_button.config(state='disabled')
        pause.set();closing.set();review_closing.set()
        status.set('Finishing this match, then opening browser approval…' if busy['value'] else 'Opening browser approval…')
    reconnect_button=ttk.Button(controls,text='Reconnect',style='Subtle.TButton',command=reconnect)
    reconnect_button.pack(side='right',padx=(8,0))
    update={'release':None,'stage':None,'checking':False}
    update_status=tk.StringVar(value='')
    def check_updates():
        if sys.platform!='win32' or update['checking']:return
        update['checking']=True;update_button.config(state='disabled');update_status.set('Checking for updates…')
        def work():
            try:
                from neptune_windows_update import check
                messages.put(('update_check',check(source.parent)))
            except Exception as error:messages.put(('update_error',str(error)))
        threading.Thread(target=work,daemon=True).start()
    def install_update():
        if busy['value'] or not update['release']:return
        update_button.config(state='disabled');update_status.set('Downloading and verifying update…')
        def work():
            try:
                from neptune_windows_update import prepare
                messages.put(('update_ready',prepare(source.parent,update['release'])))
            except Exception as error:messages.put(('update_error',str(error)))
        threading.Thread(target=work,daemon=True).start()
    update_button=ttk.Button(actions,text='Check for updates',style='Subtle.TButton',command=lambda:install_update() if update['release'] else check_updates())
    if sys.platform=='win32':
        update_button.pack(side='left',padx=(0,8))
        ttk.Label(actions,textvariable=update_status,wraplength=340,style='Muted.TLabel').pack(side='left')
        root.after(1500,check_updates)
    else:
        ttk.Label(actions,text='Updates are managed by your package manager.',style='Muted.TLabel').pack(anchor='w')
    def progress(text):messages.put(('progress',str(text)))
    def stop_current():pause.set();progress('Finishing this match, then pausing. Progress stays saved on Neptune.')
    stop_button=ttk.Button(settings,text='Stop after this match',style='Subtle.TButton',command=stop_current,state='disabled');stop_button.pack(side='left',padx=(12,0))
    def review_tracking():
        if busy['value']:messagebox.showinfo('Training is running','Finish or pause training before opening a tracking review.');return
        if reviewing.is_set():review_closing.set();return
        reviewing.set();review_closing.clear();review_button.config(text='Close tracking review')
        def review_worker():
            try:
                from neptune_identity_review import choose
                choose(HOME/'jobs',HOME/'identity-reviews',review_closing,webbrowser.open,connection=config)
            except Exception as error:progress('Tracking review: '+str(error))
            finally:reviewing.clear();messages.put(('review_closed',None))
        threading.Thread(target=review_worker,daemon=True).start()
    review_button=ttk.Button(controls,text='Review tracking…',style='Subtle.TButton',command=review_tracking);review_button.pack(side='right',padx=(8,0))
    selfchecked=[]
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
                # GPU self-check, once per session: shown here and on Neptune's Helpers & settings.
                if not selfchecked:
                    try:
                        import neptune_selfcheck,neptune_robot_jobs
                        neptune_robot_jobs.api(config,'selfcheck_put',neptune_selfcheck.run(progress))
                    except Exception as error:progress('Self-check could not finish: '+str(error)[:200])
                    selfchecked.append(True)
                from neptune_training import prepare_action_encoder
                hardware['action_features']=prepare_action_encoder(progress)
                hardware['robot_detector_sha256']=fingerprint();hardware['robot_tracking']='yolo-botsort-1'
                os.environ['NEPTUNE_TRACKING_DEVICE']='0' if hardware['device']=='cuda' else hardware['device']
                os.environ['NEPTUNE_TRAIN_DEVICE']=hardware['device']   # clip features in match tests too, not only in training
                os.environ['NEPTUNE_OCR_DEVICE']='cuda' if hardware['device']=='cuda' else 'cpu'   # number and scoreboard reading (RapidOCR)
                from neptune_engine import identity
                engine=identity();hardware['engine_version']=engine['version'];hardware['engine_sha256']=engine['sha256']
                hardware['label_contracts']=['game-builder-moments-v1'];hardware['training_protocol']='page-v2';hardware['outside_adapters']=['viper-2026-activity-v1','mapped-actions-v1','viper-2026-points-v1'];progress('Connected — ready. Choose what to run on Neptune.')
                watch_jobs(config,hardware,execute,progress,closing,pause,
                    connection=lambda value:messages.put(('connection',value)),
                    busy=lambda value:messages.put(('busy',value)),
                    failed=lambda message:progress('Needs attention: '+message),
                    device_changed=lambda:selected!=choice_value['value'] or reviewing.is_set())
            except Exception as error:
                progress('Connection needs attention: '+str(error)+' Open Neptune to check the connection. Your saved files are kept.')
                if closing.wait(15):break
        messages.put(('closed',None))
    def dashboard_worker():
        import neptune_robot_jobs
        while not closing.is_set():
            try:messages.put(('dashboard',neptune_robot_jobs.api(config,'dashboard',timeout=20)))
            except Exception:messages.put(('dashboard',None))
            if closing.wait(10):break
    ui.render_dashboard(page,{},self_id=config.get('computer_id'));page.move_to_end(bottom)
    choice_value={'value':choice.get()}
    def poll():
        choice_value['value']=choice.get()
        while not messages.empty():
            kind,message=messages.get()
            if kind=='telemetry':
                computer_card.update_readings(message);k=message.get('counters') or {}
                if k.get('passes'):
                    stage_value.set(100*((k.get('pass',1)-1)+(k.get('batch',0)/k['batches'] if k.get('batches') else 0))/k['passes']);stage_text.set('pass %s/%s · batch %s/%s%s' % (k.get('pass','?'),k['passes'],k.get('batch','?'),k.get('batches','?'),(' · '+str(k['it_s'])+' it/s') if k.get('it_s') else ''))
                elif k.get('matches'):
                    stage_value.set(100*k.get('match',0)/k['matches']);stage_text.set('match %s/%s' % (k.get('match',0),k['matches']))
                continue
            if kind=='connection':computer_card.set_connected(message);top_status.set('Connected' if message else 'Reconnecting…');continue
            if kind=='dashboard':
                if isinstance(message,dict) and isinstance(message.get('computers'),list):
                    top_status.set('Live readouts · updated '+time.strftime('%H:%M'))
                    page.clear(keep=pinned);ui.render_dashboard(page,message,self_id=config.get('computer_id'));page.move_to_end(bottom)
                else:top_status.set('Readouts unavailable · retrying')
                continue
            if kind=='closed':
                unsubscribe_meters()
                review_closing.set()
                if reconnect_requested['value']:
                    try:
                        start_reconnect_process(source)
                    except Exception as error:
                        reconnect_requested['value']=False
                        messagebox.showerror('Reconnect could not start',str(error))
                root.destroy();return
            if kind=='review_closed':review_button.config(text='Review robot tracking…');continue
            if kind=='update_check':
                update['checking']=False;update['release']=message
                update_button.config(text=('Install update '+message['version']) if message else 'Check for updates',state='normal' if not busy['value'] else 'disabled')
                update_status.set(('Version '+message['version']+' is ready to install.') if message else 'You’re up to date.');continue
            if kind=='update_error':
                update['checking']=False;update_button.config(state='normal' if not busy['value'] else 'disabled')
                update_status.set('Update check: '+message);continue
            if kind=='update_ready':
                update['stage']=message
                if busy['value']:
                    update_status.set('Update downloaded. It will install when this match finishes.');continue
                try:
                    from neptune_windows_update import launch_apply
                    launch_apply(source.parent,message);closing.set();review_closing.set();root.destroy();return
                except Exception as error:
                    update_status.set('Update install: '+str(error));update_button.config(state='normal');continue
            if kind=='busy':
                computer_card.set_working(message);job_outer.configure(height=154 if message else 62);status_label.configure(height=2 if message else 1)
                if message:
                    stage_box.pack(fill='x',pady=(4,0));progress_box.pack(fill='x',pady=(4,0));next_label.pack(fill='x',pady=(4,0))
                else:
                    stage_box.pack_forget();progress_box.pack_forget();next_label.pack_forget();job_title.set('RUNNING NOW');status.set('No assigned job')
                if not message:progress_value.set(0);remaining.set('No job running')
                busy['value']=message;resize_helper();review_button.config(state='disabled' if message else 'normal');stop_button.config(state='normal' if message else 'disabled');device.config(state='disabled' if message else 'readonly')
                if sys.platform=='win32':update_button.config(state='disabled' if message else 'normal')
                if not message and update['stage']:
                    stage=update['stage'];update['stage']=None;messages.put(('update_ready',stage))
                continue
            status.set(show_progress(message));log.config(state='normal');log.insert('end',time.strftime('%H:%M:%S')+'  '+message+'\n')
            if int(log.index('end-1c').split('.')[0])>250:log.delete('1.0','2.0')
            log.see('end');log.config(state='disabled')
        root.after(250,poll)
    def close():
        if busy['value'] and not messagebox.askyesno('Finish this match and close?','Finish the current match, save progress and close the helper?'):return
        closing.set()
        if busy['value']:pause.set();status.set('Finishing this match, saving progress, then closing…')
    root.protocol('WM_DELETE_WINDOW',close);threading.Thread(target=worker,daemon=True).start();threading.Thread(target=dashboard_worker,daemon=True).start();poll();root.mainloop()


if __name__=='__main__':main()
