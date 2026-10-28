"""Owner-paired entry point for installable Windows and Linux training helpers."""
import json
import base64
import hashlib
import os
from pathlib import Path
import queue
import re
import shutil
import sys
import threading
import time

SITE = 'https://neptunefrc.com'

# Windows opens a console window for every program the helper starts (ffmpeg, ffprobe, nvidia-smi, pip…), which
# flashes on screen over and over. Start them all without one unless a caller asks otherwise.
if sys.platform == 'win32':
    import subprocess

    class _HiddenPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault('creationflags', 0x08000000)   # CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = _HiddenPopen

# Without a console (pythonw), sys.stdout and sys.stderr are None, and any library that prints (the detector
# library, pip, PyTorch) fails with "'NoneType' object has no attribute 'write'". Send that output to a log file.
if sys.stdout is None or sys.stderr is None:
    try:
        _log_dir = Path.home() / '.neptune-trainer'; _log_dir.mkdir(parents=True, exist_ok=True)
        _log_path = _log_dir / 'helper.log'
        if _log_path.exists() and _log_path.stat().st_size > 20 * 1024 * 1024:
            _log_path.replace(_log_dir / 'helper.previous.log')
        _log = open(_log_path, 'a', encoding='utf-8', errors='replace', buffering=1)
    except OSError:
        _log = open(os.devnull, 'w')
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log


def valid_connection(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return (value.get('site') == SITE
                and re.fullmatch(r'[0-9a-f]{64}', value.get('token', '')) is not None
                and isinstance(value.get('expires_at'), int)
                and value['expires_at'] > time.time() + 60
                and isinstance(value.get('computer_id'), str))
    except (OSError, ValueError, TypeError):
        return False


def save_connection(path, grant):
    token = grant.get('access_token', '')
    if not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Neptune returned an invalid training connection.')
    payload = {'site': SITE, 'token': token,
               'expires_at': int(grant['expires_at']), 'computer_id': grant['computer_id']}
    target = Path(path)
    temporary = target.with_name(target.name + '.next')
    temporary.write_text(json.dumps(payload), encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(target)


def ensure_robot_models(credential):
    """Fetch the private tracking weights after owner pairing, never from a public EXE."""
    from neptune_yolo import bundle
    root = Path.home() / '.neptune-trainer' / 'robot-models'
    os.environ['NEPTUNE_ROBOT_MODELS'] = str(root)
    try:
        bundle(root)
        return
    except (OSError, ValueError):
        pass
    previous = Path(__file__).with_name('robot-models')
    if previous.is_dir():
        try:
            bundle(previous)
            root.mkdir(parents=True, exist_ok=True)
            for path in previous.iterdir():
                if path.is_file(): shutil.copy2(path, root / path.name)
            bundle(root)
            return
        except (OSError, ValueError):
            pass
    from neptune_trainer import api
    config = json.loads(Path(credential).read_text(encoding='utf-8'))
    rows = api(config, 'runtime_bundle', {}).get('files', [])
    if {r.get('name') for r in rows} != {'manifest.json', 'best_bumper_model.pt', 'coco_model.pt'}:
        raise ValueError('Neptune returned an incomplete robot tracking bundle.')
    root.mkdir(parents=True, exist_ok=True)
    for row in sorted(rows, key=lambda item: item['name'] == 'manifest.json'):
        name = row['name']
        data = base64.b64decode(row['data'], validate=True)
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('The robot tracking download failed its checksum.')
        target = root / name
        pending = target.with_suffix('.pending')
        pending.write_bytes(data)
        os.chmod(pending, 0o600)
        pending.replace(target)
    bundle(root)


def connect_window(path):
    import tkinter as tk
    from tkinter import ttk
    from neptune_trainer_pairing import connect_account
    import neptune_ui as ui

    root = tk.Tk()
    root.title('Connect Neptune Training Helper')
    root.geometry('560x440')      # room for the fixed-height status box and the button below it
    root.minsize(560, 440)
    ui.apply(root)
    icon = Path(__file__).with_name('Neptune.ico')
    if sys.platform == 'win32' and icon.is_file():
        try: root.iconbitmap(str(icon))
        except tk.TclError: pass
    frame = ttk.Frame(root, padding=20, style='Neptune.TFrame')
    frame.pack(fill='both', expand=True)
    ui.header(frame, logo=Path(__file__).with_name('Neptune.png'), subtitle='SECURE COMPUTER PAIRING')
    status = tk.StringVar(value='Click Connect to Neptune to begin.')
    ui.status(frame, status, detail='Approve this computer in your browser, then choose matches on Neptune.')
    events = queue.Queue()
    cancel = threading.Event()
    completed = {'value': False}

    # Reconnecting keeps this computer's record on Neptune (and its name); a first connection is named after it.
    try: previous = json.loads(Path(path).read_text(encoding='utf-8')).get('computer_id')
    except (OSError, ValueError, AttributeError): previous = None
    import platform

    def begin():
        button.config(state='disabled')
        status.set('Starting secure browser approval…')
        def worker():
            try:
                grant = connect_account(SITE, lambda message: events.put(('status', message)), cancel,
                                        computer_id=previous if isinstance(previous, str) else None, name=platform.node())
                save_connection(path, grant)
                events.put(('connected', None))
            except Exception as error:
                events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    button = ttk.Button(frame, text='Connect to Neptune', style='Neptune.TButton', command=begin)
    button.pack(anchor='w')
    root.bind('<Return>', lambda event: begin() if str(button['state']) != 'disabled' else None)
    button.focus_set()

    def poll():
        while not events.empty():
            event, value = events.get_nowait()
            if event == 'status': status.set(value)
            elif event == 'error':
                status.set(value)
                button.config(state='normal')
            elif event == 'connected':
                completed['value'] = True
                root.destroy()
                return
        root.after(200, poll)
    root.protocol('WM_DELETE_WINDOW', lambda: (cancel.set(), root.destroy()))
    poll()
    root.mainloop()
    return completed['value']


def configure_private_tools():
    if sys.platform == 'win32':
        tools = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Neptune Trainer' / 'tools' / 'bin'
        os.environ['PATH'] = str(tools) + os.pathsep + os.environ.get('PATH', '')


def main():
    configure_private_tools()
    credential = Path(__file__).with_name('trainer-connection.json')
    if '--reconnect' in sys.argv or not valid_connection(credential):
        if not connect_window(credential): return 1
    try:
        ensure_robot_models(credential)
    except Exception as error:
        from tkinter import messagebox
        messagebox.showerror('Neptune Training Helper',
                             'Robot tracking tools could not be prepared. Reopen the helper to retry.\n\n' + str(error))
        return 1
    from neptune_trainer import main as trainer_main
    trainer_main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
