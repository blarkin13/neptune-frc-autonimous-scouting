"""Shared OCR interface for the facts pipeline. Every backend runs on this computer; none is paid.

Backends
  apple-vision  helper/bin/neptune-ocr (Apple Vision, macOS 14+ on Apple Silicon), built from vision/ocr.swift.
  rapidocr      RapidOCR on ONNX Runtime with its bundled PP-OCR models (Windows, Linux, Intel Macs).

recognize(paths) returns {path: [item]} where an item is
  {'t': text, 'c': confidence 0..1 or None, 'x','y','w','h': box as fractions of the image, top-left origin}.
"""
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APPLE_BIN = Path(__file__).resolve().with_name('bin') / 'neptune-ocr'


class OcrUnavailable(ValueError):
    pass


class OcrBackend:
    name = 'none'

    def version(self) -> dict:
        raise NotImplementedError

    def recognize(self, paths) -> dict:
        raise NotImplementedError

    def describe(self) -> dict:
        return dict(self.version(), backend=self.name)


class AppleVisionBackend(OcrBackend):
    name = 'apple-vision'

    def __init__(self, binary=APPLE_BIN):
        self.binary = Path(binary)
        self._version = None

    @classmethod
    def available(cls, binary=APPLE_BIN) -> bool:
        return sys.platform == 'darwin' and platform.machine() == 'arm64' and Path(binary).is_file()

    def version(self):
        if self._version is None:
            out = subprocess.run([str(self.binary), '--version'], capture_output=True, text=True, timeout=30)
            if out.returncode != 0:
                raise OcrUnavailable('The Apple Vision text reader could not start.')
            self._version = json.loads(out.stdout)
            self._version.pop('backend', None)
        return self._version

    def _server(self):
        """One long-lived reader (--serve) instead of a launch per call; None with an older reader."""
        if getattr(self, '_serve', None) is None:
            self._serve = False
            try:
                caps = subprocess.run([str(self.binary), '--capabilities'], capture_output=True, text=True, timeout=30).stdout.split()
                if 'serve' in caps:
                    self._serve = subprocess.Popen([str(self.binary), '--serve'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            except OSError:
                pass
        if self._serve and self._serve.poll() is not None:   # it exited; start again next time
            self._serve = None
            return None
        return self._serve or None

    def recognize(self, paths):
        paths = [str(p) for p in paths]
        out = {}
        server = self._server() if paths else None
        if server:
            for path in paths:
                if '\n' in path:
                    raise OcrUnavailable('Image path contains a line break.')
                server.stdin.write(path+'\n'); server.stdin.flush()
                line = server.stdout.readline()
                if not line:
                    self._serve = None
                    raise OcrUnavailable('The Apple Vision text reader stopped.')
                d = json.loads(line)
                if d.get('file') != Path(path).name:
                    raise OcrUnavailable('The Apple Vision text reader returned results out of order.')
                if d.get('error'):raise OcrUnavailable('Apple Vision could not read an image: '+str(d['error'])[:160])
                out[path] = d.get('items', [])
            return out
        for i in range(0, len(paths), 48):
            chunk = paths[i:i + 48]
            proc = subprocess.run([str(self.binary)] + chunk, capture_output=True, text=True, timeout=900)
            if proc.returncode != 0:
                raise OcrUnavailable('The Apple Vision text reader failed: ' + (proc.stderr.strip()[:200] or 'unknown error'))
            lines = proc.stdout.splitlines()
            if len(lines) != len(chunk):
                raise OcrUnavailable('The Apple Vision text reader returned %d results for %d images.' % (len(lines), len(chunk)))
            for path, line in zip(chunk, lines):   # one line per image, in input order
                d = json.loads(line)
                if d.get('file') != Path(path).name:
                    raise OcrUnavailable('The Apple Vision text reader returned results out of order.')
                if d.get('error'):raise OcrUnavailable('Apple Vision could not read an image: '+str(d['error'])[:160])
                out[path] = d.get('items', [])
        return out


class RapidOcrBackend(OcrBackend):
    name = 'rapidocr'
    # Detector resolution: bumper digits are small, so do not shrink large crops to the 736 px default.
    # Broadcast text is upright, so the rotation classifier is off (about 10% faster, same digits on tuning frames).
    PARAMS = {'Global.log_level': 'error', 'Global.use_cls': False, 'Det.limit_type': 'max', 'Det.limit_side_len': 2000}

    def __init__(self):
        self._engine = None
        self._cv2 = None

    @classmethod
    def available(cls) -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec('rapidocr') is not None and importlib.util.find_spec('onnxruntime') is not None
        except (ImportError, ValueError):
            return False

    def _load(self):
        if self._engine is None:
            try:
                import cv2
                from rapidocr import RapidOCR
            except ImportError as error:
                raise OcrUnavailable('RapidOCR is not installed. Run the Neptune Helper installer again.') from error
            self._cv2 = cv2
            self._engine = RapidOCR(params=dict(self.PARAMS))
        return self._engine

    def version(self):
        from importlib.metadata import version
        models = sorted(p.name for p in self._models_folder().glob('*.onnx'))
        return {'rapidocr': version('rapidocr'), 'onnxruntime': version('onnxruntime'),
                'opencv': version('opencv-python-headless'), 'models': models,
                'detector_limit_side_len': self.PARAMS['Det.limit_side_len'], 'rotation_classifier': self.PARAMS['Global.use_cls']}

    @staticmethod
    def _models_folder():
        import importlib.util
        spec = importlib.util.find_spec('rapidocr')
        return Path(spec.origin).parent / 'models'

    def recognize(self, paths):
        engine = self._load()
        out = {}
        for p in paths:
            p = str(p)
            image = self._cv2.imread(p)
            if image is None:
                out[p] = []
                continue
            height, width = image.shape[:2]
            result = engine(image)
            items = []
            if result.boxes is not None and result.txts is not None:
                for box, text, score in zip(result.boxes, result.txts, result.scores):
                    xs = [float(q[0]) for q in box]
                    ys = [float(q[1]) for q in box]
                    items.append({'t': str(text), 'c': float(score), 'x': min(xs) / width, 'y': min(ys) / height,
                                  'w': (max(xs) - min(xs)) / width, 'h': (max(ys) - min(ys)) / height})
            out[p] = items
        return out


BACKENDS = {'apple-vision': AppleVisionBackend, 'rapidocr': RapidOcrBackend}


def available_backends():
    return [name for name, cls in BACKENDS.items() if cls.available()]


def select_backend(preference='auto') -> OcrBackend:
    """Apple Vision on Apple Silicon Macs, otherwise RapidOCR. Raises OcrUnavailable if neither exists."""
    if shutil.which('ffmpeg') is None:
        raise OcrUnavailable('FFmpeg is not installed. Run the Neptune Helper installer again.')
    if preference != 'auto':
        if preference not in BACKENDS:
            raise OcrUnavailable('Unknown text reader: ' + preference)
        if not BACKENDS[preference].available():
            raise OcrUnavailable('The %s text reader is not installed on this computer.' % preference)
        return BACKENDS[preference]()
    for name in ('apple-vision', 'rapidocr'):
        if BACKENDS[name].available():
            return BACKENDS[name]()
    raise OcrUnavailable('No text reader is installed. Run the Neptune Helper installer again.')
