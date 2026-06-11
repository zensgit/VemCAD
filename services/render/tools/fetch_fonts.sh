#!/usr/bin/env bash
# Fetch the OFL 仿宋/楷体 fonts (B2 decision) into services/render/fonts/.
# Pinned release archives; each font keeps its OFL license file. The image
# build tolerates absence (Noto covers CJK), so a rotted URL is non-fatal —
# it just means 仿宋/楷体 fall back until re-fetched.
#
# Usage: services/render/tools/fetch_fonts.sh
set -euo pipefail

FONTS_DIR="$(cd "$(dirname "$0")/../fonts" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Pin to specific tagged releases. Update the tag + sha intentionally (PR).
# 朱雀仿宋 (Zhuque Fangsong) — OFL.
ZQFS_URL="https://github.com/TrionesType/zhuque/releases/download/v0.214/ZhuqueFangsong-Regular.ttf"
# 霞鹜文楷 (LXGW WenKai) — OFL.
LXGW_URL="https://github.com/lxgw/LxgwWenKai/releases/download/v1.510/LXGWWenKai-Regular.ttf"

fetch() {
    local url="$1" out="$2"
    echo "fetching $out"
    if curl -fsSL --retry 3 -o "$TMP/$out" "$url"; then
        cp "$TMP/$out" "$FONTS_DIR/$out"
        echo "  -> $FONTS_DIR/$out ($(wc -c < "$FONTS_DIR/$out") bytes)"
    else
        echo "  WARN: failed to fetch $out — image will fall back to Noto for this family" >&2
    fi
}

fetch "$ZQFS_URL" "ZhuqueFangsong-Regular.ttf"
fetch "$LXGW_URL" "LXGWWenKai-Regular.ttf"
# OFL requires the license to travel with the font on redistribution.
fetch "https://raw.githubusercontent.com/TrionesType/zhuque/master/LICENSE" "ZhuqueFangsong-OFL.txt"
fetch "https://raw.githubusercontent.com/lxgw/LxgwWenKai/main/OFL.txt" "LXGWWenKai-OFL.txt"
echo "done."
