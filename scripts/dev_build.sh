#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CORE_DIR="$ROOT_DIR/deps/cadgamefusion"

if [[ ! -d "$CORE_DIR/.git" ]]; then
  echo "Missing CADGameFusion submodule at $CORE_DIR" >&2
  echo "Run: git submodule update --init --recursive" >&2
  exit 1
fi

git -C "$ROOT_DIR" submodule update --init --recursive

BUILD_DIR="${CADGF_BUILD_DIR:-$CORE_DIR/build_vcpkg_gltf}"
TOOLCHAIN_FILE=""

if [[ -n "${VCPKG_ROOT:-}" ]]; then
  TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
elif [[ -d "$CORE_DIR/vcpkg" ]]; then
  TOOLCHAIN_FILE="$CORE_DIR/vcpkg/scripts/buildsystems/vcpkg.cmake"
fi

CMAKE_ARGS=(
  -S "$CORE_DIR"
  -B "$BUILD_DIR"
  -DCMAKE_BUILD_TYPE=Release
  -DBUILD_EDITOR_QT=ON
)

if [[ -n "$TOOLCHAIN_FILE" ]]; then
  CMAKE_ARGS+=("-DCMAKE_TOOLCHAIN_FILE=$TOOLCHAIN_FILE")
fi

cmake "${CMAKE_ARGS[@]}"
cmake --build "$BUILD_DIR" --target cadgf_dxf_importer_plugin convert_cli -j

echo "Built CADGameFusion at $BUILD_DIR"
