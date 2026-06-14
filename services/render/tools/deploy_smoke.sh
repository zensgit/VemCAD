#!/usr/bin/env bash
# Post-deploy smoke for the render service. Proves a DEPLOYED endpoint is
# healthy AND reachable (the exact reachability Yuantus's worker needs) by
# exercising the real /healthz, /render and /diff over HTTP. Run it from the
# Yuantus host / network — if this passes there, RENDER_SERVICE_BASE_URL will
# work too.
#
#   bash deploy_smoke.sh http://render-host:8077
#
# Exit 0 only when all three succeed; non-zero with a reason otherwise.
set -euo pipefail

BASE="${1:?usage: deploy_smoke.sh BASE_URL   (e.g. http://127.0.0.1:8077)}"
BASE="${BASE%/}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
dxf="$tmp/sample.dxf"
# A minimal valid DXF (one LINE) — same fixture the CI image smoke uses.
printf '0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n0\nENDSEC\n0\nEOF\n' > "$dxf"

echo "== 1/3 GET /healthz =="
code="$(curl -fsS -o "$tmp/health.json" -w '%{http_code}' "$BASE/healthz" || true)"
echo "  HTTP ${code:-<unreachable>}"
[ -s "$tmp/health.json" ] && { echo "  body: $(cat "$tmp/health.json")"; }
[ "${code:-}" = "200" ] || { echo "FAIL: /healthz not 200 (unreachable or degraded — check render_cli/fonts)"; exit 1; }

echo "== 2/3 POST /render (one DXF -> PNG) =="
code="$(curl -fsS -o "$tmp/render.png" -w '%{http_code}' \
  -F "file=@$dxf;filename=sample.dxf" \
  "$BASE/render?format=png&width=400&height=300&bg=white" || true)"
sz="$(wc -c < "$tmp/render.png" 2>/dev/null || echo 0)"
echo "  HTTP ${code:-<error>}, ${sz} bytes"
{ [ "${code:-}" = "200" ] && [ "$sz" -gt 1000 ]; } || { echo "FAIL: /render did not return a PNG"; exit 1; }

echo "== 3/3 POST /diff (two DXF -> overlay PNG) =="
code="$(curl -fsS -o "$tmp/diff.png" -D "$tmp/diff.hdr" -w '%{http_code}' \
  -F "file_a=@$dxf;filename=rev_a.dxf" \
  -F "file_b=@$dxf;filename=rev_b.dxf" \
  "$BASE/diff?width=400&height=300&bg=white" || true)"
cmp="$(grep -i '^x-diff-comparable:' "$tmp/diff.hdr" 2>/dev/null | tr -d '\r' | awk '{print $2}')"
sz="$(wc -c < "$tmp/diff.png" 2>/dev/null || echo 0)"
echo "  HTTP ${code:-<error>}, comparable=${cmp:-<none>}, ${sz} bytes"
{ [ "${code:-}" = "200" ] && [ "${cmp:-}" = "true" ]; } || { echo "FAIL: /diff did not return a comparable overlay"; exit 1; }

echo
echo "OK: render service at $BASE is healthy and serving /render + /diff."
echo "Next: set Yuantus RENDER_SERVICE_BASE_URL=$BASE (must resolve + be reachable"
echo "from the Yuantus worker), then upload a DXF (preview) and diff two revisions."
