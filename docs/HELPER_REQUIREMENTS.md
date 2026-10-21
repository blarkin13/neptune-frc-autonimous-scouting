# Helper installers and requirements

The helper runs the **facts pipeline** by default on every platform: local OCR of the broadcast scoreboard, results screen and robot bumper numbers, with no AI model. The older local AI path (Ollama + qwen2.5vl:3b) remains available on Apple Silicon only, opt-in with `NEPTUNE_HELPER_PIPELINE=ai`; setup no longer downloads the 3.2 GB model by default.

`helper/requirements.json` lists supported and unsupported platforms, each prerequisite, its pinned source and SHA-256, and the OCR backend per platform. `scripts/build-helper-installers.py` builds the three packages into `.helper-build/installers/` (nothing is uploaded).

| Platform | Installer | Text reader | Prerequisites the installer checks and installs if missing |
|---|---|---|---|
| macOS 14+, Apple Silicon | `Start Neptune Helper.command` (double-click) | Apple Vision (`bin/neptune-ocr`, built from `vision/ocr.swift`) | Python 3.10+ with Tk (python.org 3.13.16 pkg); bundled FFmpeg 9.0.2 (rebuilt with fps/crop/split/format and PPM output); bundled QuickJS or existing Deno/Node; hash-pinned wheels |
| Windows 10 1809+/11, x64 | `Install Neptune Helper.cmd` → `install-neptune-helper.ps1` (per user, no admin) | RapidOCR 3.10.0 on ONNX Runtime 1.31.0 | Python 3.11+ with Tk (python.org 3.13.16, signature checked); FFmpeg 9.0.2 (gyan.dev essentials); Deno 2.9.7; hash-locked wheels from `requirements-ocr.txt`; Start menu and Desktop shortcuts |
| Ubuntu 24.04 LTS, Debian 12 (x86_64, aarch64) | `install-neptune-helper.sh` | RapidOCR 3.10.0 on ONNX Runtime 1.31.0 | apt: python3, python3-venv, python3-tk, ffmpeg, libgl1, libglib2.0-0, ca-certificates, curl; Deno 2.9.7; hash-locked wheels; `~/.local/bin/neptune-helper` and an applications-menu entry |

Not supported (the installers stop with this message): Intel Macs (Apple Vision reader is built for Apple Silicon; RapidOCR on Intel macOS is untested), Windows on ARM, Fedora/RHEL (ffmpeg-free decodes H.264 through Cisco OpenH264, untested), Ubuntu 22.04 (Python 3.10), 32-bit systems.

Every installer verifies the package's own files against `files.json` / `files.sha256` first, verifies each download's SHA-256 before use, runs `neptune_app.py --check` (platform, FFmpeg, YouTube runtime, text reader and window support) and can be re-run safely: it only installs what is missing. Uninstall options keep saved match work in `~/.neptune-helper`.

Testing status: the Mac path runs on this Apple Silicon Mac (Apple Vision and RapidOCR both evaluated). The Windows script parses cleanly in PowerShell 7.6 and the Linux script passes `bash -n`; every locked wheel resolves with matching hashes for win_amd64, manylinux x86_64 and aarch64. Neither installer has been run on a real Windows or Linux machine yet.
