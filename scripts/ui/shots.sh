#!/usr/bin/env bash
# Screenshots of the demo for UI checks (S7.12+, Lubo approved 2026-11-23).
# A throwaway headless Chromium: --rm, 1 GB / 1 CPU cap, no capabilities, non-root,
# reaches the demo on 127.0.0.1:8130 (or GG_BASE, e.g. the public URL). Writes PNGs to the folder given (default
# private/screenshots/auto, gitignored).
#   scripts/ui/shots.sh OUT_DIR name=path@WxH[:dark] ...
#   scripts/ui/shots.sh "" home=/@1280x800 case21=/case/?id=123@1280x1600:dark
set -euo pipefail
IMAGE="mcr.microsoft.com/playwright:v1.64.0-noble"
CH="/ms-playwright/chromium-1248/chrome-linux64/chrome"
OUT="${1:-}"; OUT="${OUT:-$(dirname "$0")/../../private/screenshots/auto}"; shift
mkdir -p "$OUT"; chmod 777 "$OUT"
cmds=""
for spec in "$@"; do
  name="${spec%%=*}"; rest="${spec#*=}"; path="${rest%@*}"; size="${rest##*@}"
  scheme=""; [[ "$size" == *:dark ]] && { scheme="--blink-settings=preferredColorScheme=0"; size="${size%:dark}"; }
  cmds+="$CH --headless=new --no-sandbox --disable-gpu --hide-scrollbars $scheme --virtual-time-budget=10000 --window-size=${size/x/,} --screenshot=/out/$name.png '${GG_BASE:-http://127.0.0.1:8130}$path' 2>/dev/null; "
done
docker run --rm --network host --memory 1g --cpus 1 --pids-limit 256 --cap-drop ALL \
  --security-opt no-new-privileges --user pwuser -v "$(realpath "$OUT")":/out "$IMAGE" bash -c "$cmds"
ls -1 "$OUT"
