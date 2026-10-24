"""First-run desktop setup for the Debian/Ubuntu Neptune Training Helper package."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import zipfile

SOURCE = Path('/usr/share/neptune-training-helper/app')
USER_ROOT = Path.home() / '.local/share/neptune-trainer'
APP = USER_ROOT / 'app'
VENV = USER_ROOT / 'python-environment'
TOOLS = USER_ROOT / 'tools/bin'


def prepare(progress):
    if sys.version_info < (3, 11):
        raise ValueError('Neptune Training Helper needs Python 3.11 or newer.')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ValueError('FFmpeg and FFprobe are required. Install this .deb with apt so dependencies are added.')
    if not SOURCE.is_dir():
        raise ValueError('The Neptune Training Helper package files are missing. Reinstall the .deb package.')
    USER_ROOT.mkdir(parents=True, exist_ok=True)
    version = json.loads((SOURCE / 'build-version.json').read_text())['version']
    old_version = None
    try: old_version = json.loads((APP / 'build-version.json').read_text())['version']
    except (OSError, ValueError, KeyError): pass
    if version != old_version:
        progress('Installing Neptune Training Helper ' + version + '…')
        staged = USER_ROOT / 'app-next'
        previous = USER_ROOT / 'app-before-update'
        if staged.exists(): shutil.rmtree(staged)
        shutil.copytree(SOURCE, staged)
        credential = APP / 'trainer-connection.json'
        if credential.is_file(): shutil.copy2(credential, staged / credential.name)
        if previous.exists(): shutil.rmtree(previous)
        if APP.exists(): APP.replace(previous)
        try: staged.replace(APP)
        except Exception:
            if previous.exists() and not APP.exists(): previous.replace(APP)
            raise
    python = VENV / 'bin/python3'
    if not python.is_file():
        progress('Creating a private Python environment…')
        subprocess.run([sys.executable, '-m', 'venv', str(VENV)], check=True)
    check = "from importlib.metadata import version as v; assert v('rapidocr')=='3.10.0' and v('onnxruntime')=='1.31.0' and v('yt-dlp')=='2026.8.19'"
    if subprocess.run([str(python), '-c', check], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        progress('Installing the verified text reader and video downloader…')
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-cache-dir', '--require-hashes',
                        '--only-binary=:all:', '-r', str(APP / 'requirements-ocr.txt')], check=True)
    TOOLS.mkdir(parents=True, exist_ok=True)
    if not (TOOLS / 'deno').is_file() and not shutil.which('deno') and not shutil.which('node'):
        architecture = os.uname().machine
        platform = {'x86_64': 'linux-x86_64', 'aarch64': 'linux-aarch64'}.get(architecture)
        if not platform: raise ValueError('This Linux CPU is not supported: ' + architecture)
        requirements = json.loads((APP / 'requirements.json').read_text())['requirements']
        deno = next(row for row in requirements if row['id'] == 'deno')
        url, expected = deno['sources'][platform]
        if not url.startswith('https://'): raise ValueError('The video runtime URL is invalid.')
        progress('Installing the verified YouTube video runtime…')
        pending = USER_ROOT / 'deno.zip.pending'
        with urllib.request.urlopen(url, timeout=90) as response, pending.open('wb') as output:
            # GitHub serves release files from its asset host; the checksum below proves the file either way.
            final = urllib.parse.urlparse(response.geturl())
            if final.scheme != 'https' or final.hostname not in ('github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'):
                raise ValueError('The video runtime download redirected unexpectedly.')
            shutil.copyfileobj(response, output)
        if hashlib.sha256(pending.read_bytes()).hexdigest() != expected:
            pending.unlink(missing_ok=True)
            raise ValueError('The video runtime checksum did not match.')
        with zipfile.ZipFile(pending) as archive:
            (TOOLS / 'deno').write_bytes(archive.read('deno'))
        (TOOLS / 'deno').chmod(0o755)
        pending.unlink(missing_ok=True)
    os.environ['PATH'] = str(TOOLS) + os.pathsep + os.environ.get('PATH', '')
    progress('Opening Neptune Training Helper…')
    return python, APP / 'neptune_trainer_entry.py'


def main():
    import tkinter as tk
    from tkinter import ttk
    import neptune_ui as ui
    root = tk.Tk()
    root.title('Neptune Training Helper setup')
    root.geometry('560x320')
    root.resizable(False, False)
    ui.apply(root)
    frame = ttk.Frame(root, padding=20, style='Neptune.TFrame')
    frame.pack(fill='both', expand=True)
    ui.header(frame, logo=Path('/usr/share/icons/hicolor/256x256/apps/neptune-training-helper.png'), subtitle='FIRST-LAUNCH SETUP')
    status = tk.StringVar(value='Checking this computer…')
    ui.status(frame, status, detail='Video and text tools install once for this user.', eyebrow='SETUP')
    progress = ttk.Progressbar(frame, mode='indeterminate', style='Neptune.Horizontal.TProgressbar')
    progress.pack(fill='x', pady=(4, 10))
    progress.start()
    events = queue.Queue()
    def work():
        try: events.put(('done', prepare(lambda value: events.put(('status', value)))))
        except Exception as error: events.put(('error', str(error)))
    threading.Thread(target=work, daemon=True).start()
    result = {}
    def poll():
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == 'status': status.set(value)
            elif kind == 'done': result['app'] = value; root.destroy(); return
            elif kind == 'error':
                progress.stop(); status.set(value)
                ttk.Button(frame, text='Close', style='Subtle.TButton', command=root.destroy).pack(anchor='w', pady=8)
                return
        root.after(150, poll)
    poll()
    root.mainloop()
    if 'app' not in result: return 1
    python, app = result['app']
    os.execv(str(python), [str(python), str(app), *sys.argv[1:]])


if __name__ == '__main__': raise SystemExit(main())
