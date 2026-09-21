#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_python="${SIM_ENGINE_BUILD_PYTHON:-python3.12}"
build_uv="${SIM_ENGINE_BUILD_UV:-uv}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Linux x86_64 is required for the production wheel" >&2
  exit 2
fi

source_commit="$(git -C "$repo_root" rev-parse HEAD)"
export SIM_ENGINE_GIT_COMMIT="$source_commit"
cd "$repo_root"

exec "$build_uv" run --with 'maturin>=1.7,<2.0' maturin build \
  --release \
  --locked \
  --features python \
  --compatibility manylinux_2_28 \
  --interpreter "$build_python" \
  --out "$repo_root/dist"
