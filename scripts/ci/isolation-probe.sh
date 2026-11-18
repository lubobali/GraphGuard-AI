#!/usr/bin/env bash
# CI isolation probe (S5b.2): the first step of every GraphGuard CI job.
# Fails the build if the job container can reach other containers on the box, has
# capabilities, can gain privileges, or cannot reach the package index.
# Pure bash + coreutils (runs before the toolchain is installed). Changes nothing.
set -u
fail=0
ok()  { echo "  ok    $*"; }
bad() { echo "  FAIL  $*"; fail=1; }

echo "== privileges"
capeff=$(awk '/^CapEff:/{print $2}' /proc/self/status)
nnp=$(awk '/^NoNewPrivs:/{print $2}' /proc/self/status)
[ "$capeff" = "0000000000000000" ] && ok "no capabilities (CapEff $capeff)" || bad "capabilities present: CapEff $capeff"
[ "$nnp" = "1" ] && ok "no-new-privileges" || bad "NoNewPrivs=$nnp"

echo "== network"
ips=$(hostname -I 2>/dev/null)
echo "  job address: $ips"
case " $ips" in
  *" 172.17."*) bad "job is on Docker's shared default bridge" ;;
  *" 172.25."*) bad "job is on graphguard-net" ;;
  *) ok "job has its own network" ;;
esac

# Every connection below must FAIL. Run in parallel, 1 s each.
try() { timeout 1 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null && echo "$1:$2"; }
targets=()
for h in $(seq 2 16); do for p in 5432 6379 5000 8181 5556 8081; do targets+=("172.25.0.$h $p"); done; done  # graphguard-net
for h in $(seq 2 40); do targets+=("172.17.0.$h 5000"); done                                                  # default bridge (a registry)
reached=$(for t in "${targets[@]}"; do try $t & done; wait)
if [ -z "$reached" ]; then ok "none of ${#targets[@]} container addresses reachable"
else bad "reachable from the job: $(echo $reached)"; fi

echo "== internet"
if curl -sSfI --max-time 15 https://pypi.org/simple/ >/dev/null; then ok "package index reachable"
else bad "cannot reach https://pypi.org (the job could not install anything)"; fi

[ $fail = 0 ] && echo "isolation probe: PASS" || echo "isolation probe: FAIL"
exit $fail
