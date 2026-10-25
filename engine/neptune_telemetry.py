"""Live readout for Neptune's Running now console: system meters, training counters and the last log lines.

A background reporter sends them every 5 s while a job runs (15 s while idle) with the My computers check-in,
so the site shows GPU/CPU use and pass/batch/speed even while the job loop is busy.
Nothing here affects training; every probe is best-effort and returns None when it cannot measure.
"""
import collections
import re
import shutil
import subprocess
import sys
import threading
import time

LOG = collections.deque(maxlen=14)            # (unix time, line)
STATE = {}                                    # pass, passes, batch, batches, it_s, step: set by the running job
_lock = threading.Lock()


def note(line):
    """Add a console line (also called for every helper status message)."""
    line = ' '.join(str(line).split())[:220]
    with _lock:
        if line and (not LOG or LOG[-1][1] != line):
            LOG.append((int(time.time()), line))


def update(**values):
    with _lock:
        STATE.update(values)


def clear():
    with _lock:
        STATE.clear()


def snapshot():
    with _lock:
        return dict(STATE), [list(x) for x in LOG]


def batch_counter(label, passes):
    """For a YOLO trainer: counts batches and speed into STATE; returns the callback."""
    seen = {'epoch': None, 'batch': 0, 'start': time.monotonic()}
    def on_batch(trainer):
        if seen['epoch'] != trainer.epoch:
            seen.update(epoch=trainer.epoch, batch=0, start=time.monotonic())
        seen['batch'] += 1
        took = time.monotonic()-seen['start']
        batches = len(trainer.train_loader) if getattr(trainer, 'train_loader', None) is not None else None
        update(step=label, passes=passes, batches=batches, it_s=round(seen['batch']/took, 2) if took > 0 else None,
               **{'pass': trainer.epoch+1, 'batch': seen['batch']})
    return on_batch


def epoch_line(label, trainer, passes):
    """One console line per finished pass: losses and the check score, like a training terminal."""
    parts = ['%s pass %d/%d' % (label, trainer.epoch+1, passes)]
    try:
        names = ('box', 'cls', 'dfl')
        loss = [float(x) for x in trainer.tloss]
        parts += ['%s %.3f' % (n, v) for n, v in zip(names, loss)]
    except Exception:
        pass
    metrics = getattr(trainer, 'metrics', None) or {}
    for key, name in (('metrics/mAP50(B)', 'mAP50'), ('metrics/precision(B)', 'P'), ('metrics/recall(B)', 'R')):
        if key in metrics:
            parts.append('%s %.3f' % (name, float(metrics[key])))
    note(' · '.join(parts))


# --- system meters -------------------------------------------------------------------------------------------
def _run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def nvidia():
    if not shutil.which('nvidia-smi'):
        return None
    out = _run(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits']).strip().splitlines()
    try:
        name, util, used, total, temp = [x.strip() for x in out[0].split(',')]
        return {'name': name, 'util': int(util), 'mem_used_mb': int(used), 'mem_total_mb': int(total), 'temp_c': int(temp)}
    except (IndexError, ValueError):
        return None


def apple_gpu():
    if sys.platform != 'darwin':
        return None
    out = _run(['ioreg', '-r', '-d', '1', '-w', '0', '-c', 'IOAccelerator'])
    util = re.search(r'"Device Utilization %"=(\d+)', out)
    mem = re.search(r'"In use system memory"=(\d+)', out)
    if not util:
        return None
    return {'name': 'Apple GPU', 'util': int(util[1]), 'mem_used_mb': int(mem[1])//2**20 if mem else None, 'mem_total_mb': None, 'temp_c': None}


def system():
    stats = {'gpu': nvidia() or apple_gpu()}
    try:
        import psutil
        stats['cpu'] = round(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        stats['ram_used_mb'] = (vm.total-vm.available)//2**20; stats['ram_total_mb'] = vm.total//2**20
        stats['cores'] = psutil.cpu_count()
    except Exception:
        stats['cpu'] = None
    return stats


class Reporter(threading.Thread):
    """Checks in with Neptune on a timer; `send(payload)` returns the reply (settings)."""
    def __init__(self, send, payload, on_reply, closing):
        super().__init__(daemon=True)
        self.send, self.payload, self.on_reply, self.closing = send, payload, on_reply, closing

    def run(self):
        try:
            import psutil; psutil.cpu_percent(interval=None)    # first reading primes the counter
        except Exception:
            pass
        while not self.closing.is_set():
            base = self.payload()
            state, log = snapshot()
            try:
                self.on_reply(self.send(dict(base, stats=system(), counters=state, log=log)))
            except Exception:
                pass
            pause = time.monotonic()+(5 if base.get('busy') else 15)
            while time.monotonic() < pause and not self.closing.is_set():
                time.sleep(.5)
