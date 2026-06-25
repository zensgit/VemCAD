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
# 朱雀仿宋 (Zhuque Fangsong) — OFL. v0.212+ ships a release ZIP, not a bare .ttf;
# the old v0.214 bare-.ttf pin 404s (release never existed). Extract from the ZIP.
ZQFS_ZIP_URL="https://github.com/TrionesType/zhuque/releases/download/v0.212/ZhuqueFangsong-v0.212.zip"
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

# Some upstreams (Zhuque v0.212+) publish a release ZIP rather than a bare .ttf.
# Download + extract the named .ttf into the fonts dir; non-fatal on failure
# (Noto still covers CJK, so a rotted URL / missing unzip just means fallback).
fetch_zip_ttf() {
    local url="$1" ttf="$2"
    echo "fetching $ttf (from release zip)"
    if curl -fsSL --retry 3 -o "$TMP/pkg.zip" "$url" \
        && unzip -o -j "$TMP/pkg.zip" "$ttf" -d "$TMP" >/dev/null 2>&1 \
        && [ -f "$TMP/$ttf" ]; then
        cp "$TMP/$ttf" "$FONTS_DIR/$ttf"
        echo "  -> $FONTS_DIR/$ttf ($(wc -c < "$FONTS_DIR/$ttf") bytes)"
    else
        echo "  WARN: failed to fetch/extract $ttf — image will fall back to Noto for this family" >&2
    fi
}

fetch_zip_ttf "$ZQFS_ZIP_URL" "ZhuqueFangsong-Regular.ttf"
fetch "$LXGW_URL" "LXGWWenKai-Regular.ttf"
# OFL requires the license to travel with the font on redistribution.
fetch "https://raw.githubusercontent.com/TrionesType/zhuque/master/LICENSE" "ZhuqueFangsong-OFL.txt"
fetch "https://raw.githubusercontent.com/lxgw/LxgwWenKai/main/OFL.txt" "LXGWWenKai-OFL.txt"
echo "done."
