#!/bin/bash
# Build, verify and publish a Mac helper release from the previous one, then remove old build folders.
# Usage: release-mac-helper.sh <new version> <previous version> "<release notes>"
# Example: release-mac-helper.sh 3.2.17 3.2.16 "Fixes …"
set -euo pipefail
NEW=$1; PREV=$2; NOTES=$3
R=$(cd "$(dirname "$0")/../.." && pwd)
N=/Users/brianlarkin/Documents/ChatGPT/Neptune
SPARKLE=$N/Mac-Helper-3.2.7-ready/deps/bin/generate_appcast   # keep this folder: signing tool only
PUB=${PUB_PEM:-$R/trainer-app/scripts/sparkle-pub.pem}
B=$N/Mac-Helper-$NEW-ready; OLD="$N/Mac-Helper-$PREV-ready/build/Neptune Training Helper.app"
A="$B/build/Neptune Training Helper.app"; E="$A/Contents/Resources/engine"; O=$B/public-release
ENGINE=$(cd "$R/engine" && python3 -c "import neptune_engine as e;print(e.VERSION.split('-')[0])")
BUILD=$(( $(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$OLD/Contents/Info.plist") + 1 ))

rm -rf "${B:?}"; mkdir -p "$B/build" "$O"
/bin/cp -cR "$OLD" "$A"
find "${E:?}" -maxdepth 1 -type f \( -name 'neptune_*.py' -o -name 'requirements*.json' -o -name 'requirements-*.txt' -o -name 'season_rules.json' \) -delete
for s in "$R"/engine/*; do n=$(basename "$s")
  if [ -f "$s" ] && { { [ "${n##*.}" = py ] && [ "${n#test_}" = "$n" ]; } || [ "$n" = requirements.json ] || [ "$n" = requirements-yolo.txt ] || [ "$n" = requirements-videomae.txt ] || [ "$n" = season_rules.json ]; }; then cp -p "$s" "$E/$n"; fi
done
# Shipped detectors and region data live in folders next to the engine files.
for d in field-regions field-detector robot-detector; do rm -rf "${E:?}/$d"; cp -R "$R/engine/$d" "$E/$d"; done
rm -f "${E:?}/server_run.py"; find "$A" -name __pycache__ -prune -exec rm -rf {} +
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $NEW" -c "Set :CFBundleVersion $BUILD" "$A/Contents/Info.plist"
(cd "$R/engine" && python3 -c "import json,neptune_engine;print(json.dumps(neptune_engine.identity()))") > "$A/Contents/Resources/engine-identity.json"
find "$R/engine" -name __pycache__ -prune -exec rm -rf {} +
codesign --force --sign - "$A" 2>/dev/null; codesign --verify --deep --strict "$A"

# Tests on the bundled Python, in a throwaway copy.
W=$(mktemp -d); cp -R "$R/engine" "$R/server" "$R/tests" "$W/"
(cd "$W" && ln -s server/neptune_secure neptune_secure && ln -s ../../engine server/neptune_secure/community-learning
 cd engine && PYTHONPATH=. "$A/Contents/Resources/python/bin/python3.13" -m unittest discover -p 'test_*.py' 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|FAILED|^OK") | tee "$B/tests.log"
rm -rf "${W:?}"; grep -q '^OK' "$B/tests.log"
find "$A" -name __pycache__ -prune -exec rm -rf {} +; codesign --verify --deep --strict "$A"

/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$A" "$O/Neptune-Training-Helper-$NEW.zip"
"$SPARKLE" --account neptune-training-helper --download-url-prefix https://neptunefrc.com/community/downloads/mac/ --maximum-deltas 0 "$O" | tail -1
python3 "$R/trainer-app/scripts/build-native-dmg.py" "$A" "$O/Neptune-Training-Helper.dmg" > "$B/dmg.log" 2>&1
(cd "$R/engine" && COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -czf "$O/server-engine-$ENGINE.tar.gz" $(cat SERVER_FILES.txt) neptune_robot_jobs.py neptune_robot_labels.py neptune_steps.py field-regions/*.json field-detector/reference.json field-detector/model.pt field-detector/trained_on.json robot-detector/manifest.json robot-detector/bumper_wide.pt)
python3 - "$O" "$NEW" "$PUB" <<'EOF'
import base64,re,subprocess,sys,tempfile
o,new,pub=sys.argv[1:]
sig=re.search(r'sparkle:edSignature="([^"]+)"',open(o+'/appcast.xml').read()).group(1)
f=tempfile.NamedTemporaryFile(delete=False);f.write(base64.b64decode(sig));f.close()
r=subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',pub,'-rawin','-in',f'{o}/Neptune-Training-Helper-{new}.zip','-sigfile',f.name],capture_output=True,text=True)
print(r.stdout.strip() or r.stderr.strip());sys.exit(r.returncode)
EOF
hdiutil verify "$O/Neptune-Training-Helper.dmg" >/dev/null 2>&1
cd "$O" && shasum -a 256 "Neptune-Training-Helper-$NEW.zip" appcast.xml Neptune-Training-Helper.dmg "server-engine-$ENGINE.tar.gz" > SHA256SUMS.txt
gh release create "helper-$NEW" --repo blarkin13/neptune-frc-autonimous-scouting --title "Neptune Training Helper $NEW (engine $ENGINE)" --notes "$NOTES Verify with SHA256SUMS.txt." \
  "Neptune-Training-Helper-$NEW.zip" Neptune-Training-Helper.dmg appcast.xml "server-engine-$ENGINE.tar.gz" SHA256SUMS.txt | tail -1

# Everything is on GitHub now. Keep only this build and the previous one (the next release copies it).
for d in "$N"/Mac-Helper-*-ready; do v=${d##*/Mac-Helper-}; v=${v%-ready}
  case "$v" in "$NEW"|"$PREV") ;; 3.2.7) rm -rf "${d:?}/build" ;; *) rm -rf "${d:?}" ;; esac
done
# generate_appcast keeps an unpacked copy of every release it has signed (gigabytes each time).
rm -rf "${HOME:?}/Library/Caches/Sparkle_generate_appcast"
echo "Released $NEW (engine $ENGINE). Build folders kept: $NEW, $PREV."
