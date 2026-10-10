#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_uv="${SIM_ENGINE_BUILD_UV:-uv}"
build_image="${SIM_ENGINE_MANYLINUX_IMAGE:-quay.io/pypa/manylinux_2_28_x86_64@sha256:531d7aa844bbb0c131d4ab011d3db741c4abc8d498cd5ccc86121046f62303b4}"
build_python="${SIM_ENGINE_MANYLINUX_PYTHON:-/opt/python/cp312-cp312/bin/python3.12}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Linux x86_64 is required for the production wheel" >&2
  exit 2
fi

source_commit="$(git -C "$repo_root" rev-parse HEAD)"
build_cargo_home="${CARGO_HOME:-$HOME/.cargo}"
build_rustup_home="${RUSTUP_HOME:-$HOME/.rustup}"
if command -v maturin >/dev/null 2>&1; then
  maturin_bin="$(command -v maturin)"
else
  maturin_bin="$("$build_uv" run --no-project --with 'maturin>=1.7,<2.0' which maturin)"
fi

mkdir -p "$repo_root/dist"
exec docker run --rm --user "$(id -u):$(id -g)" \
  -e CARGO_HOME=/host-cargo \
  -e RUSTUP_HOME=/host-rustup \
  -e CARGO_TARGET_DIR=/io/rust/compiler/target/manylinux_2_28 \
  -e PATH=/host-cargo/bin:/usr/local/bin:/usr/bin:/bin \
  -e SIM_ENGINE_GIT_COMMIT="$source_commit" \
  -v "$build_cargo_home:/host-cargo" \
  -v "$build_rustup_home:/host-rustup" \
  -v "$maturin_bin:/usr/local/bin/maturin:ro" \
  -v "$repo_root:/io" -w /io \
  --entrypoint /usr/local/bin/maturin "$build_image" build \
  --release \
  --locked \
  --features python \
  --compatibility manylinux_2_28 \
  --interpreter "$build_python" \
  --out /io/dist
