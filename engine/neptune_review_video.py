"""Review videos for detector training runs: what the new model does on the held-out match, uploaded with the run.

Robot detector: each held-out frame with the people's boxes and the new detector's boxes, colour-coded:
green = bumper found, red = bumper missed, yellow = box where nobody marked a bumper. Thin blue = the detector
in use, for comparison. Field detector: detected scoring targets and corners against the marked ones.
"""
from pathlib import Path

GREEN, RED, YELLOW, BLUE, WHITE, DARK = (80, 200, 90), (60, 60, 230), (40, 210, 240), (230, 150, 40), (255, 255, 255), (28, 22, 16)
WIDTH, HEIGHT, FPS, HOLD = 1280, 720, 2, 3      # each frame shown HOLD/FPS seconds


def writer(path):
    """H.264 where the platform has it (macOS), else MPEG-4 Part 2; YouTube accepts both."""
    import cv2
    for code in ('avc1', 'mp4v'):
        w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*code), FPS, (WIDTH, HEIGHT))
        if w.isOpened():
            return w
    raise RuntimeError('No video encoder available')


def fit(image):
    import cv2
    return cv2.resize(image, (WIDTH, HEIGHT))


def plain(text):
    """OpenCV's built-in font is ASCII only."""
    return str(text).replace('·', '-').replace('—', '-').replace('’', "'").encode('ascii', 'replace').decode()


def card(lines, sub=()):
    """A title card: big lines, then smaller ones."""
    import cv2
    import numpy as np
    img = np.full((HEIGHT, WIDTH, 3), DARK, np.uint8); y = 160
    for text in lines:
        cv2.putText(img, plain(text), (70, y), cv2.FONT_HERSHEY_SIMPLEX, 1.25, WHITE, 3, cv2.LINE_AA); y += 70
    y += 20
    for text in sub:
        cv2.putText(img, plain(text), (70, y), cv2.FONT_HERSHEY_SIMPLEX, .8, (200, 200, 200), 2, cv2.LINE_AA); y += 46
    return img


def banner(img, text, legend):
    import cv2
    cv2.rectangle(img, (0, 0), (WIDTH, 44), DARK, -1)
    cv2.putText(img, plain(text), (14, 30), cv2.FONT_HERSHEY_SIMPLEX, .75, WHITE, 2, cv2.LINE_AA)
    x = WIDTH-14
    for label, colour in reversed(legend):
        size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .6, 2)[0][0]; x -= size+30
        cv2.rectangle(img, (x, 14), (x+16, 30), colour, -1)
        cv2.putText(img, label, (x+22, 29), cv2.FONT_HERSHEY_SIMPLEX, .6, WHITE, 2, cv2.LINE_AA); x -= 14
    return img


def box(img, b, colour, thick=3):
    import cv2
    cv2.rectangle(img, (int(b[0]*WIDTH), int(b[1]*HEIGHT)), (int(b[2]*WIDTH), int(b[3]*HEIGHT)), colour, thick)


def match(truth, pred, iou, threshold=.3):
    """One-to-one: (found truth indexes, matched prediction indexes)."""
    found, used = set(), set()
    for i, t in enumerate(truth):
        best = max(((iou(t, p), j) for j, p in enumerate(pred) if j not in used), default=(0, None))
        if best[0] >= threshold:
            found.add(i); used.add(best[1])
    return found, used


def robot_video(out, frames, new_weights, old_weights, report):
    """frames: [(image path, truth xyxy boxes normalized)]. Returns the video path."""
    import cv2
    from ultralytics import YOLO
    from neptune_robot_jobs import detect, iou
    new = YOLO(str(new_weights)); old = YOLO(str(old_weights)) if old_weights else None
    xyxy = lambda bs: [[b['x'], b['y'], b['x']+b['w'], b['y']+b['h']] for b in bs]
    n, c = report.get('new') or {}, report.get('current')
    w = writer(out)
    pct = lambda v: '%d%%' % round(100*v) if v is not None else '-'
    intro = card(['Robot detector training run', 'Held-out match: %s' % report.get('holdout_match', '?')],
                 ['New: found %s of bumpers, %s of its boxes real (F1 %.2f)' % (pct(n.get('recall')), pct(n.get('precision')), n.get('f1', 0)),
                  ('In use: F1 %.2f' % c['f1']) if c else 'In use: the built-in detector',
                  'Result: %s' % ('switched to the new detector' if report.get('adopted') else 'kept the detector in use'),
                  'Learned from %s frames; this match was never trained on.' % report.get('train_frames', '?')])
    for _ in range(FPS*4):
        w.write(intro)
    for k, (path, truth) in enumerate(frames):
        image = cv2.imread(str(path))
        if image is None:
            continue
        pred = xyxy(detect(new, image)); found, used = match(truth, pred, iou)
        img = fit(image)
        if old:
            for b in xyxy(detect(old, image)):
                box(img, b, BLUE, 1)
        for i, t in enumerate(truth):
            box(img, t, GREEN if i in found else RED)
        for j, p in enumerate(pred):
            if j not in used:
                box(img, p, YELLOW, 2)
        banner(img, 'Frame %d of %d · found %d of %d bumpers' % (k+1, len(frames), len(found), len(truth)),
               [('found', GREEN), ('missed', RED), ('extra box', YELLOW)] + ([('in use', BLUE)] if old else []))
        for _ in range(HOLD):
            w.write(img)
    w.release()
    return Path(out)


def field_video(out, frames, new_weights, doc, report):
    """frames: [(t, image)] of the held-out match; doc: its marked regions."""
    import cv2
    import neptune_field_detector as fd
    from ultralytics import YOLO
    model = YOLO(str(new_weights))
    fmt = lambda p: 'none found' if not p or not p.get('found') else '%d of %d within %.1f%% of the marks' % (p['found'], p['expected'], 100*(p['mean_error'] or 0))
    w = writer(out)
    intro = card(['Field detector training run · %s' % report.get('game_key', ''), 'Held-out match: %s' % report.get('holdout_match', '?')],
                 ['New: %s' % fmt(report.get('new')), 'In use: %s' % (fmt(report.get('current')) if report.get('current') else 'none'),
                  'Result: %s' % ('switched to the new detector' if report.get('adopted') else 'kept the detector in use'),
                  'Learned from %s marked matches; this match was never trained on.' % report.get('matches', '?')])
    for _ in range(FPS*4):
        w.write(intro)
    marked = [fd.box_of(r['points']) for r in doc.get('regions', []) if r['kind'] == 'scoring_target']
    corners = fd.boundary_corners(doc) or []
    for k, (t, image) in enumerate(frames[:40]):
        h, wd = image.shape[:2]
        r = model.predict(image, imgsz=fd.FRAME_WIDTH, conf=fd.MIN_CONFIDENCE, verbose=False, device='cpu')[0]
        img = fit(image)
        for b in marked:
            box(img, b, GREEN, 1)
        for x, y in corners:
            cv2.circle(img, (int(x*WIDTH), int(y*HEIGHT)), 9, GREEN, 2)
        for b, c in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist()):
            nb = [b[0]/wd, b[1]/h, b[2]/wd, b[3]/h]
            if fd.CLASSES[int(c)] == 'field_corner':
                cv2.circle(img, (int((nb[0]+nb[2])/2*WIDTH), int((nb[1]+nb[3])/2*HEIGHT)), 6, YELLOW, -1)
            else:
                box(img, nb, YELLOW, 3)
        banner(img, 'Frame %d · %.0f s into the video' % (k+1, t), [('marked', GREEN), ('detected', YELLOW)])
        for _ in range(HOLD):
            w.write(img)
    w.release()
    return Path(out)


def describe(kind, report, engine):
    """YouTube title and description for a run."""
    pct = lambda v: '%d%%' % round(100*v) if v is not None else '-'
    held = report.get('holdout_match', '?')
    if kind == 'train':
        n, c = report.get('new') or {}, report.get('current')
        title = 'Robot detector run · %s · F1 %.2f%s' % (held, n.get('f1', 0), ' vs %.2f' % c['f1'] if c else '')
        body = ['Neptune Auto Scout · Robots pillar · robot (bumper) detector training run.', '',
                'Held-out match (never trained on, the same every run): %s' % held,
                'New detector: found %s of the bumpers people boxed; %s of its boxes were real bumpers (F1 %.2f).' % (pct(n.get('recall')), pct(n.get('precision')), n.get('f1', 0)),
                'Detector in use: %s' % ('F1 %.2f' % c['f1'] if c else 'the built-in one'),
                'Result: %s.' % ('switched to the new detector' if report.get('adopted') else 'kept the detector in use'),
                'Learned from %s frames in %d matches.' % (report.get('train_frames', '?'), len(report.get('matches') or [])), '',
                'Colours: green = bumper found, red = bumper missed, yellow = a box where nobody marked a bumper, thin blue = detector in use.']
    else:
        title = 'Field detector run · %s · %s' % (report.get('game_key', ''), held)
        body = ['Neptune Auto Scout · Field pillar · field detector (scoring targets and field corners) training run.', '',
                'Game: %s · held-out match (never trained on, the same every run): %s' % (report.get('game_key', ''), held),
                'Result: %s.' % ('switched to the new detector' if report.get('adopted') else 'kept the detector in use'), '',
                'Colours: green = marked by people, yellow = detected by the new model.']
    body += ['', 'Engine %s. Match footage: FIRST Robotics Competition broadcast.' % engine]
    return title[:100], '\n'.join(body)[:4900]
