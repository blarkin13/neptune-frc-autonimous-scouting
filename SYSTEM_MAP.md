# System map

## Pipeline (engine/)

```
match video
  → neptune_facts / neptune_ocr      OCR facts: game clock, roster, score bug, bumper numbers
  → neptune_clock.align              video time ↔ match clock (joins outside scouting timestamps)
  → neptune_yolo / neptune_tracking  YOLO + BoT-SORT robot tracks; neptune_identity assigns team numbers
  → neptune_temporal.plan            4 s clips per tracked robot
  → neptune_videomae / R3D-18        frozen clip embeddings
  → neptune_training                 PU-bagging diagonal-LDA action heads (one per Game Builder action)
  → neptune_events                   decode clip scores into timed actions
  → neptune_scoring_model            kernel-ridge score head → per-robot points
  → reports, benchmark gate (Q7 reserved)
```

Labels: Game Builder (`neptune_video_labels`, `neptune_action_labels`, `neptune_games`, `season_rules.json`)
and outside scouting imports (`neptune_learning`, `neptune_review_learning`).

Runtimes: the Mac trainer (`neptune_trainer.py`, `neptune_training_gui.py`, `neptune_app.py`) and the
server worker (`server_run.py`, `install-server.sh`, run by `neptune-community-learning.service`).

## Server (server/)
- `neptune_secure/community-*.php`: catalog, video tags, pairing of trainers, training control/progress,
  external scouting import, score model, robot models, model management.
- `public_html/Neptune/community/`: tag-video, review-tags, training-labels, scouting-results, connect pages.
- `public_html/Neptune/admin/community-*.php`, `api/community-*.php`: admin and JSON API.

- `public_html/Neptune/autoscout/`: the Auto Scout section, three pillars: `robot-labels.php` (1 · Robots),
  `scoring-areas.php` (2 · Field), `train.php` (3 · Actions; `?view=test`, `?view=helpers`). Shared blocks:
  `community/pillar.php` + `community/assets/pillar.js`, data from `train.php?overview`.
- `neptune_secure/robot-detector-jobs.php` + `api/robot-detector.php`: detector jobs for helpers; field detectors
  are stored per `game_key`. Folder layout on the Mac and AWS: `docs/HANDOFF.md`.

## Known problems (from reviews/2026-10-20-auto-scout)
- Action heads near chance on held-out data.
- Robot identity coverage is concentrated in close-ups and auto; wide shots are weak.
- Labels confounded with alliance and camera; some train/eval contamination; metrics not informative.
- Recommended next step: identity v2 (native-resolution wide-shot OCR plus bracket-verified contact).

See `data-pointers/README.md` for where the data lives.
