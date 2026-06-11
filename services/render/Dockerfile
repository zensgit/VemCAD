# vemcad-render — Linux container image (Phase 1 A6).
#
# Three stages so the font layer (the A6 novelty: CJK fonts present on the
# Linux render host) can be built + verified in seconds via
#   docker build --target fonts -t vemcad-render-fonts .
# while the heavy render_cli compile (stage `builder`) runs in CI / the
# registry build, not on a dev machine.
#
# Build context = the VemCAD repo root (the submodule deps/cadgamefusion must
# be checked out recursively):
#   docker build -f services/render/Dockerfile -t vemcad-render .

# ── Stage 1: builder — compile render_cli from the cadgamefusion submodule ──
FROM debian:bookworm-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build \
        qt6-base-dev qt6-svg-dev libgl1-mesa-dev \
        libeigen3-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# deps/cadgamefusion is a submodule; copy the whole tree so its own submodule
# (deps/libdxfrw) and CMake project are available.
COPY deps/cadgamefusion /src/cadgamefusion
RUN cmake -S /src/cadgamefusion -B /build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DBUILD_EDITOR_QT=ON \
    && cmake --build /build --target render_cli -j "$(nproc)" \
    # Stage render_cli + the cadgamefusion-built shared libs it links
    # (libcore.so, libcore_c.so, libdxfrw.so, …) — the binary alone fails at
    # runtime with "libcore_c.so: cannot open shared object file".
    && mkdir -p /artifacts/bin /artifacts/lib \
    && cp /build/editor/qt/render_cli /artifacts/bin/render_cli \
    && find /build -name '*.so*' -type f -exec cp -v {} /artifacts/lib/ \;

# ── Stage 2: fonts — runtime base with CJK fonts (verifiable standalone) ────
FROM debian:bookworm-slim AS fonts
ENV DEBIAN_FRONTEND=noninteractive
# Qt6 runtime + offscreen platform deps + fontconfig + Noto CJK (OFL, Debian
# package — guarantees 黑体/宋体 + CJK fallback without a network fetch).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libqt6gui6 libqt6svg6 libqt6core6 \
        qt6-qpa-plugins \
        libgl1 libegl1 \
        fontconfig fonts-noto-cjk \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Bundled OFL 仿宋/楷体 (朱雀仿宋 / 霞鹜文楷) — fetched into services/render/fonts/
# by tools/fetch_fonts.sh (NOT committed; see fonts/README.md). Optional: the
# build tolerates an empty dir (Noto still covers CJK).
COPY services/render/fonts/ /usr/share/fonts/vemcad/
RUN fc-cache -f && fc-list :lang=zh | sort | head -n 40

# ── Stage 3: runtime — the service + render_cli ─────────────────────────────
FROM fonts AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /artifacts/bin/render_cli /usr/local/bin/render_cli
COPY --from=builder /artifacts/lib/ /usr/local/lib/
RUN ldconfig
WORKDIR /app
COPY services/render/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
COPY services/render/app /app/app
COPY services/render/README.md /app/README.md
# Linux canonical isolation is asserted at `docker run --network none`;
# RENDER_ASSUME_NO_NETWORK makes the render report record it honestly.
ENV QT_QPA_PLATFORM=offscreen \
    RENDER_CLI_PATH=/usr/local/bin/render_cli \
    RENDER_ASSUME_NO_NETWORK=1 \
    RENDER_CACHE_DIR=/var/cache/vemcad-render \
    PYTHONUNBUFFERED=1
RUN mkdir -p /var/cache/vemcad-render
EXPOSE 8077
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8077/healthz').status==200 else 1)" || exit 1
CMD ["python3", "-m", "uvicorn", "app.main:app", "--factory", "--host", "0.0.0.0", "--port", "8077"]
