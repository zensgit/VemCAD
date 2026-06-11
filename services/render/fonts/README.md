# Bundled fonts (render service A6)

The container's CJK coverage comes from two places:

1. **Noto Sans/Serif CJK** — installed via the Debian `fonts-noto-cjk`
   package in the image (OFL; covers 黑体/宋体 families + a CJK fallback so
   no glyph is ever missing). No fetch needed.
2. **仿宋 / 楷体 (OFL)** — `朱雀仿宋` and `霞鹜文楷`, the B2 font decision
   (2026-06-10). These are **not** in Debian and are **not committed** to the
   repo (size + keep git clean). `tools/fetch_fonts.sh` downloads pinned
   release archives into this directory; the Dockerfile `fonts` stage copies
   whatever `*.ttf/*.otf/*.ttc` are present here into the image.

The image build **tolerates an empty `fonts/`** — Noto still covers CJK, the
仿宋/楷体 families simply fall back. Render reports record the actual resolved
family (B1 two-layer record), so a missing 仿宋 is visible, not silent.

## License

Both 朱雀仿宋 and 霞鹜文楷 are SIL Open Font License 1.1 — redistribution in
the image is permitted. Keep each font's `LICENSE`/`OFL.txt` alongside it when
fetched (fetch_fonts.sh does this). Do NOT add non-OFL/commercial fonts here;
those follow the contract §8 intranet-render-only path (per-tenant store via
`--font-dir`), not the baked-in image.

This directory is git-ignored except this README and `.gitkeep`.
