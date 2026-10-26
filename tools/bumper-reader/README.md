# Local bumper-number review

Uses the already-installed `qwen2.5vl:3b` model through Ollama on `127.0.0.1:11434`. The model sees only a bumper crop, without roster hints. Results are suggestions for human review, never OCR anchors, saved corrections, or training labels. This tool does not change the helper's automatic tracking pipeline.

Start the server with `ollama serve`. Run one request at a time on the 8 GB Mac; avoid concurrent model training.

From the repository root:

```sh
python3 tools/bumper-reader/read.py --manifest local/robot-labels/manifest.json \
  --match 2026txcmp1_qm4 --output local/ollama-bumpers-review --limit 6
```

Or supply a bumper crop with `--image /absolute/path/crop.png` instead of `--manifest`. Use a new output directory each time. The tool writes `suggestions.json`, the exact input crops, and `report.html`. Images/results belong under ignored `local/`, not git. Q7 is excluded from manifest experiments.

The report retains the source image hash, source-video hash when available, crop coordinates, model digest, raw response, and timing. Partial, malformed, or unreadable readings cannot produce a team suggestion. Even a complete reading requires visual confirmation. A model's readable/complete flags are self-reports, not measured confidence. Number correctness and useful speed must be evaluated before any tracking integration.

This command uses a 2,048-token context and unloads the model after two idle minutes. It does not download models or call cloud inference. The Ollama service itself remains available until stopped; it has not been configured to start at login.
