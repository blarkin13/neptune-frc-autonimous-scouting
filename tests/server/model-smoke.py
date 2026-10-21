"""Manual local-model smoke test; not an accuracy benchmark. No network except loopback."""
import argparse
import base64
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'helper'))
from neptune_helper import infer
p = argparse.ArgumentParser()
p.add_argument('--frame', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
content = [{'type': 'text', 'text': 'Inspect the attached image. Read the largest displayed RED alliance score and BLUE alliance score. Return a JSON object with red_score and blue_score as integers, or null if unreadable, and a short explanation describing the actual image. Do not guess.'}, {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(a.frame.read_bytes()).decode()}}]
r = infer('http://127.0.0.1:11434/v1/chat/completions', 'qwen2.5vl:3b', content)
a.output.write_text(json.dumps(r, indent=2))
print('Local multimodal response received; saved for inspection. This does not establish match-analysis accuracy.')
