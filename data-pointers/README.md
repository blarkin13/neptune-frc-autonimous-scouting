# Where the data lives (pointers only)

## This Mac
- Trainer jobs, label snapshots, reports: `~/.neptune-trainer/jobs/`
- Prepared features, localizations: `~/.neptune-trainer/cache/<id>/{features,prepared,localizations}`
  (source videos and tracking facts are removed by the media-cleanup policy)
- R3D / VideoMAE weights: under `~/.neptune-trainer/`
- Installed trainer: `~/Downloads/Neptune Trainer`, Python env in
  `~/Library/Application Support/Neptune Trainer/python-environment`

## AWS host (ip-172-31-14-32)
- Production site `/var/www/neptune/`; QA `/var/www/neptune-qa/`; uploads `/var/www/neptune/maintenance-uploads/`
- Server worker code: `neptune_secure/community-learning/` under the site; service `neptune-community-learning.service`
- Private robot models: `neptune_secure/community-learning/robot-models/` (manifest copied here as
  `robot-models.manifest.json`; weights are not in git)
- Database: MySQL `scouting` (`community_*` tables; official per-robot truth for evaluation in
  `augur_epa_alliance_samples`)

## Unknown, to fill in
- Exact worker install path and Python env on the host (`systemctl cat neptune-community-learning.service`)
- Server-side training caches and model output paths
- Any cron jobs or importers that feed the pipeline
