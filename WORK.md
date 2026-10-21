# Work log (newest first)

## 2026-10-21 — Claude: match quality reports
- Added `engine/neptune_quality.py` + `engine/test_quality.py` (10 tests) and `docs/match-quality.md`:
  a per-match clock-join check, and a per-match count/points report against reference labels and the video's
  score bug. Read-only; no engine fingerprints change.
- Ran the clock check on the qm1/qm3/qm4 facts: all `usable`. The first version counted the held 2:20/0:00
  reads as failures (33–68% "rejected"); fixed to count only rejects while the clock runs.
- Not done: running it on the ViperScout matches (facts deleted; reprocess first); wiring the verdict into
  training so `exclude` matches are skipped automatically (that changes `neptune_training.py`, which
  invalidates cached preparation, so it should land as its own reviewed change).
- Noticed: training still stores `team_priors` in the scoring head as provenance (`neptune_training.py:701`).
  `predict` does not use it, but it is team history; worth removing.

## 2026-10-21 — Claude: repo created
- Moved autonomous scouting out of `neptune-frc-scouting` into this repo. Engine `2.4.0-review-learning-preview2` (I said 2.2.8 earlier; that is the trainer app build). It includes the
  local working-tree edits that were never committed in the main repo (the PU head gates and scoring
  changes), because `helper/` there is untracked and this was the only copy.
- Checked: `scripts/sync-to-neptune.sh … --check` reports no differences against the main repo.
- Open: see "Known problems" in `SYSTEM_MAP.md`; the review is in `reviews/`.
