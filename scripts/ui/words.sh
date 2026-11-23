#!/usr/bin/env bash
# S7.18: words a person sees on first load (main area; closed <details> do not count), per page.
#   scripts/ui/words.sh /  "/case/?id=2273022"  /review/  /manager/
set -euo pipefail
# prose = outside tables (the alert list and data tables are content, not explanation)
COUNT='(()=>{const w=t=>t.split(/\s+/).filter(Boolean).length;const m=document.querySelector("main");let t=0;m.querySelectorAll("table").forEach(x=>t+=w(x.innerText));return "all "+w(m.innerText)+" prose "+(w(m.innerText)-t)})()'
for path in "$@"; do
  n=$("$(dirname "$0")/clickshot.sh" "$path" 1280x900 "wait:2500" "eval:$COUNT" 2>&1 | sed -n 's/^eval:.* -> //p' | tr -d '"' | tail -1)
  echo "$path $n"
done
