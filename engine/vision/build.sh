#!/bin/sh
# Builds helper/bin/neptune-ocr for Apple Silicon, macOS 14+. Needs Xcode Command Line Tools
# on the build machine only; contributors get the prebuilt binary in the helper bundle.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/../bin"
swiftc -O -target arm64-apple-macos14 "$here/ocr.swift" -o "$here/../bin/neptune-ocr"
codesign --force --sign - "$here/../bin/neptune-ocr" 2>/dev/null || true
echo "built $here/../bin/neptune-ocr"
