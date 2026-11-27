#!/usr/bin/env bash
# Click-then-screenshot (S7.14+), same throwaway capped container as shots.sh.
#   scripts/ui/clickshot.sh <path> <WxH> [dark] "click:button|Next" "shot:name" ...
set -euo pipefail
IMAGE="mcr.microsoft.com/playwright:v1.64.0-noble"
OUT="$(dirname "$0")/../../private/screenshots/auto"; mkdir -p "$OUT"; chmod 777 "$OUT"
path="$1"; shift
docker run --rm --network host --memory 1g --cpus 1 --pids-limit 256 --cap-drop ALL \
  --security-opt no-new-privileges --user pwuser -e CH=/ms-playwright/chromium-1248/chrome-linux64/chrome \
  -v "$(realpath "$OUT")":/out -v "$(realpath "$(dirname "$0")")/clickshot.mjs":/clickshot.mjs:ro \
  "$IMAGE" node /clickshot.mjs "${GG_BASE:-http://127.0.0.1:8130}$path" "$@"
