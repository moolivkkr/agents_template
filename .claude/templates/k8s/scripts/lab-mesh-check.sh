#!/bin/bash
# lab-mesh-check.sh — prove the lab Macs reach each other over the tailnet, every pair, both ways.
# Read-only apart from a throwaway HTTP listener per Mac (killed at the end). Run from any lab Mac.
#
#   MACS="bookbridgeadmin@macstudio51 macm4 studio52 studio256" .claude/templates/k8s/scripts/lab-mesh-check.sh
#
#   MACS   [user@]mac for each lab Mac (tailnet names; user@ when its login differs from yours)
#   PORT   test port for the HTTP listener (default 18999): proves arbitrary TCP gets through each
#          Mac's pf rules and application firewall, not only the ports someone already opened
#
# Per pair (source -> target):  path   direct or DERP-relayed, and latency (tailscale ping)
#                                ssh    tcp/22 answers (pf io.landos + Remote Login)
#                                http   an HTTP GET to the target's listener on PORT succeeds
set -uo pipefail
MACS="${MACS:?set MACS=\"[user@]mac ...\"}"
PORT="${PORT:-18999}"
TS='$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)'
SELF="$(eval "$TS" status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].split(".")[0])')"
mac_of() { local e="${1#*@}"; echo "${e%%:*}"; }
run_on() {   # <[user@]mac> <command>
  if [ "$(mac_of "$1")" = "$SELF" ]; then bash -c "$2"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$1" "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH; $2"; fi
}
PASS=0; FAIL=0
ok()  { printf '  PASS %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  FAIL %s\n' "$1"; FAIL=$((FAIL+1)); }

echo "== reachability of each Mac from $SELF (ssh is how this check drives the others)"
REACH=()
for e in $MACS; do
  if run_on "$e" true 2>/dev/null; then REACH+=("$e"); ok "$(mac_of "$e"): ssh as ${e%%@*}"
  else bad "$(mac_of "$e"): cannot run commands there (ssh); its rows are skipped"; fi
done

echo "== listeners on :$PORT"
for e in ${REACH[@]+"${REACH[@]}"}; do
  run_on "$e" "pkill -f 'http.server $PORT' 2>/dev/null; cd /tmp && nohup python3 -m http.server $PORT --bind 0.0.0.0 >/tmp/lab-mesh-check.log 2>&1 & sleep 1; nc -z -G 3 127.0.0.1 $PORT" \
    && ok "$(mac_of "$e") listening" || bad "$(mac_of "$e") listener did not start"
done
cleanup() { for e in ${REACH[@]+"${REACH[@]}"}; do run_on "$e" "pkill -f 'http.server $PORT'" >/dev/null 2>&1; done; }
trap cleanup EXIT

for src in ${REACH[@]+"${REACH[@]}"}; do
  echo "== from $(mac_of "$src")"
  for dst in $MACS; do
    [ "$src" = "$dst" ] && continue
    d="$(mac_of "$dst")"
    path="$(run_on "$src" "$TS ping -c 1 --timeout 8s $d 2>&1 | tail -1")"
    case "$path" in
      *"via DERP"*) bad "$d path RELAYED (works, but slow): $path" ;;
      pong*) ok "$d path ${path#pong from }" ;;
      *) bad "$d unreachable on the tailnet: $path" ;;
    esac
    ip="$(run_on "$src" "$TS ip -4 $d 2>/dev/null | head -1")"
    run_on "$src" "nc -z -G 6 $ip 22" >/dev/null 2>&1 && ok "$d ssh (tcp/22)" || bad "$d ssh (tcp/22) dropped: pf io.landos or Remote Login"
    case " ${REACH[*]-} " in *" $dst "*)
      code="$(run_on "$src" "curl -s -m 8 -o /dev/null -w '%{http_code}' http://$ip:$PORT/")"
      [ "$code" = 200 ] && ok "$d http :$PORT" || bad "$d http :$PORT -> ${code:-no answer} (pf or application firewall)" ;;
    esac
  done
done

echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
