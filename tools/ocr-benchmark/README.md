# OCR benchmark

`truth.json` holds what a person read on saved frames (Claude, 2026-10-26):

- **Bumpers:** 160 labelled bumper boxes (at least 70 px wide), chosen with a fixed seed from the 82 reviewed robot-label frames of 2026txcmp1 Q3 and Q4. Each box has its team number and a legibility grade: `full` (73: every digit readable), `partial` (39: readable only with the roster in mind), `none` (48: no number visible). `none` boxes measure false reads.
- **Scoreboard:** clock, red score and blue score on 88 frames: those 82 frames plus 6 frames from 2026capoh qm9, 2026ctwat qm32 (blue-left overlay) and 2026txsan qm2.

Images stay under the main checkout's `local/` and are checked against their SHA-256 before use. Q7 is not included. Official results are not used. The settings in `neptune_ocr` were tuned on this set, so it is a development benchmark, not a held-out test.

```sh
python tools/ocr-benchmark/benchmark.py --images ../../local --backend apple-vision --out local/ocr-benchmark/after-apple-vision.json
python tools/ocr-benchmark/benchmark.py --images ../../local --backend rapidocr --no-generic --methods track-crop,tiles   # the earlier behaviour
python tools/ocr-benchmark/benchmark.py --truth tools/ocr-benchmark/truth-heldout.json --images ../../local --backend apple-vision   # held-out event
```

`truth-heldout.json` is a held-out set from another event, never used for tuning: 156 bumper boxes on 2026capoh_qm9 (Phoenix, different camera and overlay). The boxes come from the shipped bumper detector (confidence at least 0.35, at least 70 px wide, below the overlay), one frame every 4 s, and the numbers were read by eye (Claude, 2026-10-27): 99 `full`, 24 `partial`, 33 `none`. Its frames live in `local/ocr-benchmark/heldout-capoh/`. Most readable boxes are team 5025, so it measures one event's look more than six teams evenly.

The Python needs OpenCV and, for `--backend rapidocr`, `engine/requirements-ocr.txt`. The benchmark uses the built-in game rules, not an installed game pack.

## Results, 2026-10-26

Bumpers, correct reads (wrong reads in brackets):

| Reader | Method | Full (73) | Partial (39) | False reads on no-number boxes (48) |
|---|---|---|---|---|
| Apple Vision | tracker crop before | 36 (1) | 0 (1) | 0 |
| Apple Vision | wide-shot tiles | 32 (2) | 0 | 0 |
| Apple Vision | **new bumper read** | **57 (0)** | **5 (0)** | **0** |
| RapidOCR | tracker crop before | 57 (2) | 12 (1) | 4 |
| RapidOCR | wide-shot tiles | 60 (2) | 10 (1) | 1 |
| RapidOCR | **new bumper read** | **67 (0)** | **15 (0)** | **1** |

Scoreboard, 88 frames (clock, then 176 scores):

| Reader | Before: clock / scores right, wrong, unread | After |
|---|---|---|
| Apple Vision | 88 / 162, 2, 12 | 88 / 168, 0, 8 |
| RapidOCR | 88 / 176, 0, 0 | 88 / 176, 0, 0 |

The two wrong scores were swapped red and blue: a ctwat frame (blue on the left) matched the Week 0 profile (red on the left). Apple Vision's remaining misses are single-digit scores it does not detect as text, and one AGE frame.

## Held-out event and score re-read, 2026-10-27

Bumpers on the held-out event (2026capoh_qm9), correct reads (wrong reads in brackets):

| Reader | Method | Full (99) | Partial (24) | False reads on no-number boxes (33) |
|---|---|---|---|---|
| Apple Vision | tracker crop before | 22 (0) | 1 (0) | 0 |
| Apple Vision | wide-shot tiles | 18 (0) | 0 | 0 |
| Apple Vision | **new bumper read** | **84 (0)** | **3 (0)** | **0** |
| RapidOCR | tracker crop before | 76 (2) | 3 (1) | 1 |
| RapidOCR | wide-shot tiles | 76 (1) | 5 (0) | 0 |
| RapidOCR | **new bumper read** | **98 (0)** | **4 (0)** | **0** |

The gain held on an event the settings never saw.

Scoreboard: when a frame has a clock and both alliance labels but no score on one side, the score box alone is cropped, enlarged 3x and read again (`neptune_facts.reread_scores`); inside that box a lone O is a zero. Apple Vision scores went from 168 right, 0 wrong, 8 unread to **172, 0, 4**. RapidOCR stays at 176 of 176. A wider crop was tried and rejected: it pulled in clock digits and read 20 for a zero.

The one remaining RapidOCR false read (txcmp1 Q3) is a lit driver-station sign (3679) above a false bumper detection. A colour-saturation filter was tried and rejected: the overexposed sign digits measured less saturated (0.08-0.14) than a real white bumper number (0.52), so it dropped a correct read and kept the false one. The tracker's identity gates (two exact moments, conflicting reads drop the track) remain the protection.
