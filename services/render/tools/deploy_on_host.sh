#!/usr/bin/env bash
# One-shot deploy + verify of the VemCAD render service on THIS host, so Yuantus
# can be pointed at it. scp it to the host where Yuantus runs (or any box Yuantus
# can reach) and run it. Needs: docker + curl. Idempotent (safe to re-run).
#
#   bash deploy_on_host.sh
#   PORT=8077 BIND=127.0.0.1 bash deploy_on_host.sh           # host-local (Yuantus on same host)
#   NETWORK=yuantus_default bash deploy_on_host.sh            # Yuantus runs in docker on this net
#   IMAGE=ghcr.io/zensgit/vemcad-render:<sha> bash deploy_on_host.sh   # pin a build for rollback
#
# Zero-risk rollback:  docker rm -f vemcad-render   + unset Yuantus RENDER_SERVICE_BASE_URL
#
# SECURITY (Phase 1): the service has NO auth. It binds 127.0.0.1 by default —
# keep it on a trusted internal network; do not publish it to a public iface.
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/zensgit/vemcad-render:main}"
NAME="${NAME:-vemcad-render}"
PORT="${PORT:-8077}"            # host port for the local health smoke
BIND="${BIND:-127.0.0.1}"      # host interface to publish on
NETWORK="${NETWORK:-}"         # optional: a docker network Yuantus is on

bold(){ printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok(){   printf '\033[32m%s\033[0m\n' "$*"; }
fail(){ printf '\033[31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || fail "docker not found on this host"
command -v curl   >/dev/null || fail "curl not found on this host"

bold "1/4  pull $IMAGE"
docker pull "$IMAGE"

bold "2/4  (re)create container '$NAME'"
docker rm -f "$NAME" >/dev/null 2>&1 || true
args=(-d --name "$NAME" --restart unless-stopped -p "$BIND:$PORT:8077")
[ -n "$NETWORK" ] && args+=(--network "$NETWORK")
docker run "${args[@]}" "$IMAGE" >/dev/null
ok "started"

BASE="http://$BIND:$PORT"
bold "3/4  wait for /healthz"
body=""
for _ in $(seq 1 30); do
  body="$(curl -fsS "$BASE/healthz" 2>/dev/null)" && break
  body=""; sleep 2
done
[ -n "$body" ] || { docker logs "$NAME" 2>&1 | tail -20; fail "/healthz never came up"; }
echo "  $body"
echo "$body" | grep -q '"status":"ok"' || fail "/healthz degraded (render_cli/fonts — see body above)"
ok "healthz ok"

bold "4/4  smoke /render + /diff"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
printf '0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n0\nENDSEC\n0\nEOF\n' > "$tmp/s.dxf"
c="$(curl -fsS -o "$tmp/r.png" -w '%{http_code}' \
  -F "file=@$tmp/s.dxf;filename=s.dxf" "$BASE/render?format=png&width=400&height=300&bg=white" || true)"
{ [ "$c" = 200 ] && [ "$(wc -c <"$tmp/r.png")" -gt 1000 ]; } || fail "/render did not return a PNG (HTTP $c)"
ok "/render OK ($(wc -c <"$tmp/r.png") bytes)"
c="$(curl -fsS -o "$tmp/d.png" -D "$tmp/d.hdr" -w '%{http_code}' \
  -F "file_a=@$tmp/s.dxf;filename=a.dxf" -F "file_b=@$tmp/s.dxf;filename=b.dxf" \
  "$BASE/diff?width=400&height=300&bg=white" || true)"
cmp="$(grep -i '^x-diff-comparable:' "$tmp/d.hdr" 2>/dev/null | tr -d '\r' | awk '{print $2}')"
{ [ "$c" = 200 ] && [ "$cmp" = true ]; } || fail "/diff did not return a comparable overlay (HTTP $c, comparable=$cmp)"
ok "/diff OK (comparable=$cmp)"

if [ -n "$NETWORK" ]; then YBASE="http://$NAME:8077"; else YBASE="http://$BIND:$PORT"; fi
bold "DONE — render service is healthy and serving /render + /diff"
cat <<EOF
Point Yuantus at it and restart the worker:
    RENDER_SERVICE_BASE_URL=$YBASE
$( [ -n "$NETWORK" ] \
   && echo "  (Yuantus must be on docker network '$NETWORK')" \
   || echo "  (Yuantus must run on THIS host; if it's in docker, re-run with NETWORK=<yuantus_net>)" )
Then in Yuantus: upload a DXF (high-fidelity preview), and diff two revisions via
    GET /api/v1/cad/files/{file_id}/visual-diff?other_file_id=<RevB>
Rollback (instant, zero-risk): unset RENDER_SERVICE_BASE_URL + restart worker;  docker rm -f $NAME
EOF
