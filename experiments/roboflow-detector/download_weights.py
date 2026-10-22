"""Download the candidate using Roboflow's documented SDK (requires access)."""
import os
from pathlib import Path


def main():
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        raise SystemExit("Set ROBOFLOW_API_KEY locally; do not paste it into chat.")
    from roboflow import Roboflow

    target = Path(__file__).resolve().parent / "candidate-weights"
    target.mkdir(exist_ok=True)
    os.chdir(target)
    version = Roboflow(api_key=key).workspace("frc-robot-recognition").project(
        "frc-robot-detection-6-hjmz0"
    ).version(21)
    models = version.models()
    if not models:
        raise SystemExit("Roboflow returned no downloadable models for version 21.")
    if len(models) != 1:
        raise SystemExit("Multiple models returned; select the YOLO11 Nano model explicitly.")
    models[0].download()
    print("Downloaded candidate artifacts to", target)


if __name__ == "__main__":
    main()
