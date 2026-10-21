# Neptune autonomous scouting

Turns FRC match video into scouting: either **auto tag scouting** (per-robot actions plus a score estimate)
or **auto traditional scouting** (filled-in scouting forms). Scores are counted from what the video shows.

Training material: pre-labeled match videos (Game Builder labels) and outside scouting data (for example
ViperScout), joined to the video by reading the game clock in the frames and matching it to the action
timestamps in the scouting data.

## Layout

| Folder | What it is | Installed to (main repo `neptune-frc-scouting`) |
|---|---|---|
| `engine/` | The one Python engine (2.2.8): OCR facts, tracking, clips, models, scoring, trainer | `helper/` (Mac trainer) **and** `neptune_secure/community-learning/` (server worker, files in `engine/SERVER_FILES.txt`) |
| `server/` | PHP endpoints, community and admin pages, training-control JS | `neptune_secure/`, `public_html/Neptune/` |
| `server/sql/` | Migrations for the `community_*` tables | `sql/` |
| `tests/server/` | PHP/JS tests for the server side | `tests/community-analysis/` |
| `trainer-app/` | macOS trainer build and publish scripts | `scripts/` |
| `docs/` | Design notes and workflow docs | `docs/community-analysis/` |
| `reviews/` | Independent reviews, evidence and patches | (not deployed) |
| `data-pointers/` | Where data lives; manifests only, never data | (not deployed) |

Engine tests: `cd engine && python3 -m pytest -q` (or `python3 -m unittest`).

## Deploying a change

This repo is the place to work. Production still installs from the main repo, so:

```sh
scripts/sync-to-neptune.sh ~/Documents/ChatGPT/Neptune/neptune-frc-scouting --check   # see what would change
scripts/sync-to-neptune.sh ~/Documents/ChatGPT/Neptune/neptune-frc-scouting           # copy it over
```

Then ship from the main repo the usual way (Release Center / GitHub mirror).

## Rules

See `AGENTS.md`. They apply to people, Codex and Claude alike.

## Compatibility links

`neptune_secure`, `public_html`, `tests/community-analysis` and `server/neptune_secure/community-learning`
are symlinks so code and tests that use the main repo's paths run unchanged here. The sync script skips them.

## Test status at import (2026-10-21)

Same as the main repo: engine 331 tests with 7 errors (numpy/tkinter not installed in the system Python);
server PHP 26 of 29 pass (`catalog`, `maintenance-package`, `training-progress-mysql` fail in both).
