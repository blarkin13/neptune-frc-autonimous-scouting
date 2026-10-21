#!/bin/bash
# Neptune's double-click setup/launcher. No commands need to be typed by the user.
set -euo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONNOUSERSITE=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_CONFIG_FILE=/dev/null
cd -- "$(dirname -- "$0")"
launch_dir="$PWD"
setup_root="${NEPTUNE_HELPER_SETUP_ROOT:-$HOME/Library/Application Support/Neptune Helper}"
failed() {
  printf '\nNeptune setup could not finish. Your matches have not been submitted.\n'
  printf 'Please share the error above with the Neptune owner. You can double-click this file to retry.\n'
  if [[ -t 0 ]]; then read -r -p 'Press Return to close.' _unused; fi
}
trap failed ERR
if [[ "$(uname -s)" != Darwin ]]; then
  printf 'This setup file is for Apple Silicon Macs. Use the Windows or Linux installer instead.\n'
  exit 1
fi
if [[ "$(uname -m)" != arm64 || "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" != 1 ]]; then
  printf 'Intel Macs are not supported. Neptune Helper reads match videos with Apple Vision on Apple Silicon (M-series) Macs.\n'
  exit 1
fi
os_major="$(sw_vers -productVersion | cut -d. -f1)"
if (( os_major < 14 )); then printf 'Neptune Helper requires macOS 14 or newer.\n'; exit 1; fi
printf '\nNeptune Helper — checking this Mac\n\n'
python_bin=''
for candidate in /Library/Frameworks/Python.framework/Versions/{3.15,3.14,3.13,3.12,3.11,3.10}/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import sys, tkinter, venv, ssl; assert sys.version_info >= (3,10)' 2>/dev/null; then
    python_bin="$candidate"
    break
  fi
done
if [[ -z "$python_bin" ]]; then
  if [[ "${1:-}" == --verify-only ]]; then printf 'Python with window support is missing; normal startup will install it.\n'; exit 2; fi
  printf 'Installing missing Python and window support. macOS will show the official installer.\n'
  mkdir -p "$setup_root/downloads"
  python_url="$(plutil -extract requirements.0.source raw -o - requirements.json)"
  python_sha="$(plutil -extract requirements.0.sha256 raw -o - requirements.json)"
  case "$python_url" in https://www.python.org/ftp/python/*.pkg) ;; *) printf 'Unexpected Python source in requirements document.\n'; exit 1;; esac
  python_pkg="$setup_root/downloads/python.pkg"
  if [[ ! -f "$python_pkg" ]] || [[ "$(shasum -a 256 "$python_pkg" | cut -d' ' -f1)" != "$python_sha" ]]; then
    curl --fail --location --proto '=https' --proto-redir '=https' --retry 3 --connect-timeout 30 --progress-bar "$python_url" -o "$python_pkg.partial"
    actual_sha="$(shasum -a 256 "$python_pkg.partial" | cut -d' ' -f1)"
    if [[ "$actual_sha" != "$python_sha" ]]; then printf 'Python download did not pass verification. Retry setup.\n'; exit 1; fi
    mv "$python_pkg.partial" "$python_pkg"
  fi
  pkgutil --check-signature "$python_pkg"
  open -W -a Installer "$python_pkg"
  python_bin=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
  "$python_bin" -c 'import tkinter, venv, ssl' || { printf 'Python installation was not completed. Double-click this launcher to retry.\n'; exit 1; }
fi
printf 'Python and window support are ready.\n'
# Check every packaged file before launching or installing dependencies.
"$python_bin" - "$launch_dir" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);manifest=json.loads((root/'files.json').read_text())
for name,expected in manifest.items():
    path=root/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit('A setup file is missing or changed: '+name+'. Download and unzip the helper again.')
print('Included tools and setup files verified.')
PY
if [[ "${1:-}" == --verify-only ]]; then printf 'Launcher checks passed. No software was installed or started.\n'; exit 0; fi
mkdir -p "$setup_root"
venv_dir="$setup_root/python-environment"
if [[ ! -x "$venv_dir/bin/python3" ]] || ! "$venv_dir/bin/python3" -c 'import tkinter, ssl' 2>/dev/null; then
  printf 'Creating Neptune’s private environment…\n'
  "$python_bin" -m venv --clear "$venv_dir"
fi
if ! "$venv_dir/bin/python3" -c 'import certifi, yt_dlp_ejs; from importlib.metadata import version; assert certifi.__version__ == "2026.07.22"; assert version("yt-dlp") == "2026.8.19"' 2>/dev/null; then
  printf 'Installing missing video and connection support from the included requirements file…\n'
  "$venv_dir/bin/python3" -m pip install --no-index --no-cache-dir --require-hashes --find-links "$launch_dir/wheels" -r "$launch_dir/requirements.txt"
fi
if ! "$launch_dir/bin/neptune-ocr" --version >/dev/null 2>&1; then
  printf 'The Apple Vision text reader (bin/neptune-ocr) could not start. If macOS blocked it, approve it in System Settings > Privacy & Security, then double-click this launcher again.\n'
  exit 1
fi
printf 'Apple Vision text reader is ready.\n'
printf '\nOpening Neptune Helper. It checks the video tools and the text reader. No AI model download is needed.\nKeep this window open.\n\n'
"$venv_dir/bin/python3" "$launch_dir/neptune_app.py"
