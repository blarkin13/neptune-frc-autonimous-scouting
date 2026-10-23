# Handoff: where things live (updated 2026-10-23)

Read `AGENTS.md` first (rules), then `SYSTEM_MAP.md`, then the top of `WORK.md`.

## Source of truth

- **GitHub:** `blarkin13/neptune-frc-autonimous-scouting` (public), branch `main`. Everything below is in it
  except data, weights and secrets (see `data-pointers/`).
- `engine/` is the Python engine: the helper app's engine *and* the server worker's engine (one copy).
- `server/` mirrors the live site: `server/public_html/Neptune/…` → `/var/www/neptune/public_html/Neptune/…`,
  `server/neptune_secure/…` → `/var/www/neptune/neptune_secure/…`.
- `trainer-app/` builds the Mac helper. `local/` (git-ignored) holds smoke-test data and the site package.

## Owner's Mac

| Path | What |
|---|---|
| `~/Desktop/autonomous_scouting` | this repo (work here) |
| `~/Documents/ChatGPT/Neptune/Mac-Helper-<ver>-ready/` | helper release builds. Only the newest two are kept |
| `~/Documents/ChatGPT/Neptune/Mac-Helper-3.2.7-ready/deps/` | Sparkle `generate_appcast` (signing tool). **Keep** |
| `~/Documents/ChatGPT/Neptune/Windows-Helper-*`, `Roboflow-detector-trial` | older work, not used by the current build |
| `~/.neptune-trainer/` | the helper's data: `cache/`, `jobs/`, `identity-reviews/`, `robot-detector/` (adopted bumper detector), `field-detector/<game_key>/` (adopted field detector + `reference.json`), `*-detector-work/` (deleted 6 h after a run) |
| `~/Library/Logs/Neptune Training Helper/helper.log` | helper log |
| `/Applications/Neptune Training Helper.app` | installed helper (updates via Sparkle) |

The old Codex folder `~/Documents/ChatGPT/Neptune` is **no longer the code location**. Code moved to the repo.

## AWS (`/var/www/neptune`)

| Path | What |
|---|---|
| `public_html/Neptune/autoscout/` | Auto Scout section (owner only): `index.php` hub, `robot-labels.php` (**1 · Robots**), `scoring-areas.php` (**2 · Field**), `train.php` (**3 · Actions**; `?view=test` Test & release; `?view=helpers` Helpers & settings) |
| `public_html/Neptune/community/` | Watch & tag (`?view=catalog`, `tag-video.php`), saved tags (`?view=results`, `scouting-results.php`), `layout.php` (Auto Scout menu), `pillar.php` + `assets/pillar.js` (pillar status/model/runs blocks) |
| `public_html/Neptune/admin/community-learning.php`, `admin/scoring-areas.php` | 308 redirects to `autoscout/` |
| `public_html/Neptune/api/robot-detector.php` | helper API: detector jobs (claim/progress/finish), adopt, current, current_field (per `game_key`) |
| `public_html/Neptune/api/robot-labels.php`, `api/field-regions.php` | helper API: labels and scoring-area documents |
| `public_html/Neptune/community/downloads/mac/` | helper ZIPs, DMG, `appcast.xml`; each ZIP needs a `<Files>` grant in `.htaccess` |
| `neptune_secure/community-learning/` | server engine (same files as `engine/`, listed in `engine/SERVER_FILES.txt`) incl. `season_rules.json` |
| `neptune_secure/robot-detector/<org>/` | `requests/`, `current/` (bumper detector), `history/`, `field-current/<game_key>/`, `field-history/<game_key>/`, `prefill/`, `undone/` |
| `neptune_secure/robot-labels/<org>/`, `robot-labels/seed/` | bumper boxes per YouTube video |
| `neptune_secure/field-regions/<user>/`, `field-regions/seed-documents/` | scoring-area documents |

## How changes reach users

- **Website:** `local/site-autoscout/` (manifest of files + known live hashes, `install.py`) → tarball
  uploaded to the GitHub release `site-autoscout-section` → owner runs one curl/sha256/`install.py` line on AWS.
  The installer refuses if any live file differs from a known version, backs up what it replaces.
- **Helper + server engine:** `trainer-app/scripts/release-mac-helper.sh <new> <prev> "<notes>"` builds from the
  previous app, runs all tests on the bundled Python, signs (pinned Sparkle key), makes ZIP/appcast/DMG/
  `server-engine-<ver>.tar.gz`, publishes GitHub release `helper-<ver>`, and deletes old build folders.
  The owner then installs it on AWS (download, sha256 check, copy ZIP/DMG/appcast, `.htaccess` grant, unpack
  engine into `neptune_secure/community-learning`, restart `neptune-community-learning.service`).

## Current state

- Helper **3.2.20**, engine **2.7.7-2025-layouts**. Released on GitHub; AWS install pending on the owner.
- Three pillars: Robots (shared bumper detector) → Field (one field detector per `game_key`) → Actions
  (action + scoring models per season). Seasons/games come only from `engine/season_rules.json`.
- 2025 REEFSCAPE broadcast layouts added (standard FIRST, FIRST in Michigan). Other district overlays may
  need their own profile. 2026 profiles unchanged.
- **Built locally, not yet packaged:** the pillar layout (commit `b9d6539`). Owner wanted to see it first.
- "Run on Neptune" (server-side training/tests) was removed 2026-10-23: everything runs on helpers. Auto Scout access is owner/admin of the owner organization, without the extra Google step.
- Open: "Unknown instead of zero" when a robot is barely tracked (proposed, not built); 2025 tracking not run
  end to end; 2027 game is `configured: false` until released.

## Using Codex / ChatGPT without access to the Mac

- **Codex cloud** works on the GitHub repo directly: give it the repo, it makes a branch and a pull request.
  Fine for engine, site and test changes. It cannot reach AWS, the owner's helper data, or the signing key,
  so it can't publish helper releases or install on AWS. Merge its PR, then build/publish from the Mac.
- **ChatGPT with the GitHub connector** can read the repo and answer questions or draft changes.
- Tests that need no video/GPU: `cd engine && PYTHONPATH=. python -m unittest discover -p 'test_*.py'`
  (a few need cv2/torch/ultralytics; the bundled helper Python has them).
