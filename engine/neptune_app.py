"""Single packaged entry point: native window, worker, or bundle verification."""
import json
import os
from pathlib import Path
import sys


def main():
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    from neptune_setup import configure_tools, resources
    configure_tools()
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        sys.argv.pop(1)
        # macOS windowed bundles unset stdout; workers still use redirected OS pipes.
        sys.stdout = os.fdopen(os.dup(1), 'w', buffering=1)
        sys.stderr = os.fdopen(os.dup(2), 'w', buffering=1)
        if os.name == 'nt':
            import signal

            def interrupt(*_):
                raise KeyboardInterrupt
            signal.signal(signal.SIGBREAK, interrupt)
        import neptune_helper
        try:
            return neptune_helper.main() or 0
        except Exception as exc:
            print('ERROR '+(str(exc) if isinstance(exc,ValueError) else 'Processing failed. Check the connection, video source and local engine.'),flush=True)
            return 1
    if len(sys.argv) > 1 and sys.argv[1] == '--self-test':
        import subprocess
        results = {}
        for tool in ['ffmpeg', 'ffprobe']:
            output = subprocess.check_output([str(resources() / 'vendor/bin' / tool), '-version'], stderr=subprocess.STDOUT, timeout=15).decode()
            results[tool] = output.splitlines()[0]
        results['runtime'] = (resources() / 'vendor/runtime/ollama').is_file()
        import tkinter
        window = tkinter.Tk()
        window.withdraw()
        results['tk'] = str(window.tk.call('info', 'patchlevel'))
        window.destroy()
        results['python'] = sys.version
        Path(sys.argv[2]).write_text(json.dumps(results, indent=2))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        # Installer verification: platform, video tools, YouTube runtime, text reader and window support.
        from neptune_setup import LocalSetup
        setup = LocalSetup()
        setup.check_tools(print)
        import neptune_ocr
        backend = neptune_ocr.select_backend()
        print('Text reader:', json.dumps(backend.describe()))
        import tkinter
        window = tkinter.Tk()
        window.withdraw()
        print('Window support: Tk', window.tk.call('info', 'patchlevel'))
        window.destroy()
        print('Neptune Helper check passed.')
        return 0
    # Prevent two windows from racing over this contributor's saved reservation.
    state = Path.home() / '.neptune-helper'
    state.mkdir(mode=0o700, exist_ok=True)
    lock = (state / 'app.lock').open('a+')
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    try:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        root.withdraw()
        messagebox.showinfo('Neptune Helper', 'Neptune Helper is already open.')
        root.destroy()
        return 0
    from neptune_helper_gui import HelperWindow
    HelperWindow(root)
    root.mainloop()
    lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
