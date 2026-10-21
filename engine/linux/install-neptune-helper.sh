#!/usr/bin/env bash
# Neptune Helper installer and launcher for Linux.
#
# Supported (checked before anything is installed):
#   Distributions: Ubuntu 24.04 LTS, Debian 12   (apt-based; system Python 3.11+ with Tk)
#   CPU:           x86_64 (amd64) and aarch64 (arm64)
# Not supported: Fedora/RHEL (their ffmpeg-free package depends on Cisco OpenH264 for H.264 decoding, which
# this installer has not been tested with), Ubuntu 22.04 (Python 3.10), 32-bit systems.
#
# What it does, checking each prerequisite first and installing only what is missing:
#   1. System packages via apt (asks for your password through sudo): python3, python3-venv, python3-tk,
#      ffmpeg, libgl1, libglib2.0-0, ca-certificates, curl
#   2. Deno (yt-dlp's YouTube JavaScript runtime), SHA-256 checked, into ~/.local/share/neptune-helper/tools
#   3. A private Python environment with hash-locked RapidOCR, ONNX Runtime and yt-dlp wheels
#   4. The helper self-check, a launcher at ~/.local/bin/neptune-helper and a desktop entry
# Usage: ./install-neptune-helper.sh [--uninstall] [--no-desktop]
set -euo pipefail
export PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${XDG_DATA_HOME:-$HOME/.local/share}/neptune-helper"
tools="$data/tools/bin"
venv="$data/python-environment"
app="$data/app"
launcher="$HOME/.local/bin/neptune-helper"
desktop="${XDG_DATA_HOME:-$HOME/.local/share}/applications/neptune-helper.desktop"

step() { printf '\n\033[36m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32mOK\033[0m  %s\n' "$1"; }
fail() { printf '\n  \033[31m%s\033[0m\n' "$1" >&2; exit 1; }

if [[ "${1:-}" == --uninstall ]]; then
  step 'Removing Neptune Helper (saved match work in ~/.neptune-helper is kept)'
  rm -rf "$data" "$launcher" "$desktop"
  ok 'Removed the launcher, desktop entry, private environment, tools and app files. System packages were left installed.'
  exit 0
fi

# ---- 1. This computer -----------------------------------------------------------------------------
step 'Checking this computer'
[[ -r /etc/os-release ]] || fail 'Cannot identify this Linux distribution (/etc/os-release is missing).'
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:24.04|debian:12) ;;
  *) fail "Unsupported distribution: ${PRETTY_NAME:-unknown}. Supported: Ubuntu 24.04 LTS and Debian 12." ;;
esac
arch="$(uname -m)"
case "$arch" in
  x86_64) platform=linux-x86_64 ;;
  aarch64|arm64) platform=linux-aarch64 ;;
  *) fail "Unsupported CPU architecture: $arch. Supported: x86_64 and aarch64." ;;
esac
free_kb="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
(( free_kb > 3 * 1024 * 1024 )) || fail 'Free at least 3 GB of disk space in your home folder, then retry.'
ok "${PRETTY_NAME}, $arch, $((free_kb / 1024 / 1024)) GB free"

# ---- 2. Package integrity ----------------------------------------------------------------------------
step 'Verifying the downloaded package'
command -v sha256sum >/dev/null || fail 'sha256sum is missing (coreutils).'
while read -r expected name; do
  [[ -f "$package/$name" ]] || fail "A setup file is missing: $name. Download and unpack Neptune Helper again."
  actual="$(sha256sum "$package/$name" | cut -d' ' -f1)"
  [[ "$actual" == "$expected" ]] || fail "A setup file changed: $name. Download and unpack Neptune Helper again."
done < "$package/files.sha256"
ok 'All package files match their checksums'

# ---- 3. System packages -----------------------------------------------------------------------------
step 'Checking system packages'
needed=(python3 python3-venv python3-tk ffmpeg libgl1 libglib2.0-0 ca-certificates curl)
missing=()
for p in "${needed[@]}"; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || missing+=("$p")
done
if (( ${#missing[@]} )); then
  printf '  Installing: %s\n' "${missing[*]}"
  if [[ $EUID -eq 0 ]]; then sudo_cmd=(); else command -v sudo >/dev/null || fail 'sudo is needed to install system packages.'; sudo_cmd=(sudo); fi
  "${sudo_cmd[@]}" apt-get update
  "${sudo_cmd[@]}" apt-get install -y --no-install-recommends "${missing[@]}"
fi
python3 -c 'import sys, tkinter, venv, ssl; assert sys.version_info >= (3, 11)' 2>/dev/null || fail 'System Python 3.11+ with Tk is not usable.'
ffmpeg -version >/dev/null 2>&1 && ffprobe -version >/dev/null 2>&1 || fail 'FFmpeg is installed but does not run.'
ok "Python $(python3 -c 'import platform; print(platform.python_version())'), FFmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"

# ---- 4. Deno --------------------------------------------------------------------------------------------
step 'Checking the YouTube video runtime'
mkdir -p "$tools"
if "$tools/deno" --version >/dev/null 2>&1; then ok 'Deno already installed'
elif command -v deno >/dev/null || command -v node >/dev/null; then ok 'Using the installed Deno or Node.js'
else
  read -r url sha < <(python3 - "$package/app/requirements.json" "$platform" <<'PY'
import json, sys
req = {r['id']: r for r in json.load(open(sys.argv[1]))['requirements']}
url, sha = req['deno']['sources'][sys.argv[2]]
print(url, sha)
PY
)
  [[ "$url" == https://* ]] || fail 'Unexpected Deno source.'
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  curl --fail --location --proto '=https' --proto-redir '=https' --retry 3 --progress-bar "$url" -o "$tmp/deno.zip"
  [[ "$(sha256sum "$tmp/deno.zip" | cut -d' ' -f1)" == "$sha" ]] || fail 'The Deno download did not pass its SHA-256 check. Retry setup.'
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extract("deno", sys.argv[2])' "$tmp/deno.zip" "$tools"
  chmod 755 "$tools/deno"
  "$tools/deno" --version >/dev/null || fail 'Deno was installed but does not run.'
  ok 'Installed Deno'
fi

# ---- 5. App files and private Python environment ----------------------------------------------------
step 'Installing Neptune Helper and its text reader'
rm -rf "$app"; mkdir -p "$data"; cp -R "$package/app" "$app"
if ! "$venv/bin/python3" -c 'import tkinter, ssl' 2>/dev/null; then
  rm -rf "$venv"; python3 -m venv "$venv"
fi
if ! "$venv/bin/python3" -c "from importlib.metadata import version as v; assert v('rapidocr')=='3.10.0' and v('onnxruntime')=='1.31.0' and v('yt-dlp')=='2026.8.19'" 2>/dev/null; then
  "$venv/bin/python3" -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r "$app/requirements-ocr.txt" \
    || fail 'Python packages could not be installed. Check the internet connection and retry.'
fi
ok 'RapidOCR, ONNX Runtime and video download support installed'

# ---- 6. Self-check ------------------------------------------------------------------------------------
step 'Running the helper self-check'
if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  "$venv/bin/python3" "$app/neptune_app.py" --check || fail 'The self-check failed. Share the messages above with the Neptune owner.'
else
  printf '  No graphical session found; skipping the window check.\n'
  "$venv/bin/python3" -c "import sys; sys.path.insert(0, '$app'); import neptune_setup, neptune_ocr; neptune_setup.LocalSetup().check_tools(print); print(neptune_ocr.select_backend().describe())" \
    || fail 'The self-check failed. Share the messages above with the Neptune owner.'
fi

# ---- 7. Launcher and desktop entry -------------------------------------------------------------------
step 'Creating the launcher'
mkdir -p "$(dirname "$launcher")"
cat > "$launcher" <<EOF
#!/usr/bin/env bash
exec "$venv/bin/python3" "$app/neptune_app.py" "\$@"
EOF
chmod 755 "$launcher"
if [[ "${1:-}" != --no-desktop ]]; then
  mkdir -p "$(dirname "$desktop")"
  cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Neptune Helper
Comment=Analyse FRC match videos on this computer
Exec="$launcher"
Icon=applications-science
Terminal=false
Categories=Utility;Education;
EOF
  command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$desktop")" >/dev/null 2>&1 || true
  ok "Desktop entry: Neptune Helper (applications menu); launcher: $launcher"
fi
printf '\n\033[32mNeptune Helper is installed.\033[0m Open it from your applications menu or run neptune-helper.\n'
printf 'Run this installer again at any time; it only installs what is missing.\n'
