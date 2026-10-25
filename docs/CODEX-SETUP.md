# Note for Codex: how this Mac and repo are set up

Read `AGENTS.md` (owner rules), `SYSTEM_MAP.md` (what talks to what) and the top of `WORK.md` (latest work) first.
`docs/HANDOFF.md` has deeper history.

## Owner rules that bite
- Scores are counted from video; official totals are for evaluation only (scoreboard moments are a tagging aid).
- `2026txcmp1_qm7` is reserved. Do not weaken release gates.
- No data, weights, videos or secrets in git (`.gitignore` blocks `*.pt`, `*.mp4`, `*.zip`, `*.dmg`, `*.deb`, `*.exe`, `*token*`, `/local/`).

## Repo: `~/Desktop/autonomous_scouting` → GitHub `blarkin13/neptune-frc-autonimous-scouting` (branch `main`)
| Path | What it is |
|---|---|
| `engine/` | Python engine shared by every helper (Mac, Windows, Linux) and the server. `neptune_engine.py` holds `VERSION` and `FILES` (the list that ships — add new modules there). Tests: `engine/test_*.py`. |
| `server/` | The live site's code, mirrored from AWS: `server/public_html/Neptune/…` (pages, `api/`, `community/assets/*.js/css`) and `server/neptune_secure/…` (PHP classes, data folders outside the web root). |
| `trainer-app/` | Helper apps: `macos/NeptuneTrainingHelper/App.swift` + `native_worker.py`, `windows/`, `linux/bootstrap.py`, `common/` (entry + pairing), `scripts/` (build/release). |
| `tests/server/*.php` | Plain PHP checks (`php tests/server/x.php`). catalog, maintenance-package, temporal-model and training-progress-mysql need MySQL/network and fail locally — expected. |
| `docs/`, `WORK.md`, `SYSTEM_MAP.md` | Docs and the work log (add a dated entry for each change). |
| `local/` (git-ignored) | `local/site-autoscout/` = the website install package (see below). |
| `neptune_secure/`, `public_html/` at repo root | Old untracked copies — ignore; edit under `server/`. |

## Outside the repo (on this Mac)
- `~/Documents/ChatGPT/Neptune/` — release outputs and private material:
  - `Mac-Helper-<ver>-ready/`, `Windows-Helper-<ver>-ready/`, `Linux-Helper-<ver>-ready/` — built packages (keep ~2 each).
  - `Windows-Helper-6.4.2-ready/Neptune-Trainer-Windows.zip` — base for every Windows build. `Linux-Helper-6.5-ready/base-linux-6.4.zip` — base for Linux.
  - `apt-signing/` — the apt repo GPG key (never in git). Fingerprint B8A7E4785EBA7365D304DB09285D71BC67B4458B.
- Bundled Python for running tests: `~/Documents/ChatGPT/Neptune/Roboflow-detector-trial/Neptune Detector Trial.app/Contents/Resources/python/bin/python3.13` (system python3 has no pytest/torch).
- Helper data on any machine: `~/.neptune-trainer/` (caches, jobs, `helper.log` on Windows).

## Running tests
```
cd engine && PYTHONPATH=. "<bundled python>" -m unittest discover -p 'test_*.py' </dev/null
cd trainer-app/scripts && "<bundled python>" -m unittest test_installable_trainer test_windows_update
for t in tests/server/*.php; do php $t >/dev/null || echo FAIL $t; done
```
After any `train.php` markup change, check every `$('id')` in `training-control.js` exists in `train.php` (it stops at the first missing one; `modal-video-help` is made at runtime).

## Releasing (bump the version, build, commit, push, publish, then give the owner AWS commands)
- **Engine:** bump `VERSION` in `engine/neptune_engine.py`.
- **Mac:** `bash trainer-app/scripts/release-mac-helper.sh <new> <prev> "<notes>"` — builds, signs (Sparkle), runs tests, publishes GitHub release `helper-<new>` (zip, dmg, appcast.xml, server-engine tarball), prunes build folders. It publishes, so get the owner's OK first.
- **Windows:** bump `VERSION` in `trainer-app/scripts/build-windows-training-helper.py`, then
  `build-windows-training-helper.py --base <6.4.2 zip> --output <dir>`, `build-windows-exe.py <dir>/Neptune-Trainer-Windows.zip <dir>/Neptune-Training-Helper-Setup.exe`, write SHA256SUMS, `gh release create helper-windows-<ver> <dir>/*`.
- **Linux:** bump `VERSION` in `build-linux-deb.py`, build the .deb from the base zip, `build-apt-repo.py <deb> <dir>/apt`, tar `apt/` contents to `apt-repo.tar.gz` (`COPYFILE_DISABLE=1 tar --no-xattrs`), `gh release create helper-linux-<ver>`.
- **Website:** `local/site-autoscout/` holds `files/` (copies of server files), `manifest.json` (each file's sha256 plus `allowed_live` = earlier versions the live copy may be), `patches.json` (targeted edits for live files that drifted from the repo), `install.py`. To update: copy changed `server/` files into `files/`, append the old sha to `allowed_live`, set the new sha, then
  `tar -czf site-autoscout.tar.gz -C site-autoscout .` (install.py at top level) and upload it to the `site-autoscout-section` release under a unique name `site-autoscout-<sha12>.tar.gz` (the release URL is CDN-cached; reusing a name serves stale files).
- **AWS** (the owner runs these as root, via SSM): download from the GitHub release, `sha256sum -c`, then install — site: `python3 install.py`; Mac: zip/dmg/appcast into `community/downloads/mac`, engine into `neptune_secure/community-learning`; Windows: setup/zip/update/latest.json into `community/downloads/windows` (+ `.htaccess` allow); Linux: replace `public_html/Neptune/apt`. Copy the exact blocks from the last release in WORK.md/the transcript, changing versions and hashes.

## Where things live on the live site
- Auto Scout pages: `/autoscout/robot-labels.php` (1 · Robots), `scoring-areas.php` (2 · Field), `train.php` (3 · Actions, `?view=test`, `?view=helpers`).
- Shared status/summary UI: `community/pillar.php` + `community/assets/pillar.js` (data from `train.php?overview=1`).
- Helper API: `api/robot-detector.php` (detector jobs, `computer_poll` live readings, keep-awake settings), action jobs via `community-trainers.php`.
- Detector queue and per-computer files: `neptune_secure/robot-detector/<org>/` (requests/, current/, field-current/<game>/, computers/, selfchecks/).

## Habits
- Ask before publishing anything (GitHub releases, uploads, pushes).
- Preview page changes locally: `.claude/launch.json` `site-php` serves a scratch copy; feed sample data by overriding `fetch` for `?overview=1`.
- Keep comments short and match the surrounding code style.
