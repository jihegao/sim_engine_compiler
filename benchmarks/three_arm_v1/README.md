# Same-Rust dispatch ablation and IR reuse (Issue 6)

This is a new pilot based on PR25 `9737822`, preserving its F35 no-index CPU
window. It reuses the existing scan, indexed blocked-cache and opt-in candidate
paths with identical shared preparation. Defaults and historical adoption
thresholds are unchanged. See [protocol](PROTOCOL.md) for the separate semantic,
measurement and prospective performance gates, and [source audit](SOURCE_AUDIT.md)
for the authentic J35 input. Generated results are separate from that snapshot.

- `workloads.py`: bounded synthetic low-contention/sparse/dense families and
  persisted Business IR edits for frequency, resources and process composition.
- `admission.py`: current three-layer compilation, independent Python reference,
  exact Rust three-arm/profile/observation/thread checks, source/build/evidence
  binding, and diagnostic counters. This does not run formal timing.
- `driver.py`: consumes admitted artifacts, freezes the matrix, executes one
  time-limited uninstrumented window, retains incomplete cells on failure.
- `summarize.py`: reports every frozen cell and paired prospective thresholds.

Build the current checkout's MLIR plugins using pinned LLVM/MLIR 23.1.1, and
build Rust with `cargo +1.90.0 build --locked --release --manifest-path
rust/runtime/Cargo.toml --bin sim-engine-runtime --bin stage-c-benchmark`.
Run the required regression/reuse/control suites before admission. Preserve
actual logs and the build/semantic receipt; passing an empty status marker is
not admission. The final report records exact commands and artifact hashes.

```sh
.venv/bin/python benchmarks/three_arm_v1/verify.py \
  --plugin-dir tools/mlir_dispatch/build-issue6 \
  --mlir-opt /tmp/issue6-llvm-23.1.1/bin/mlir-opt
PYTHONPATH=src .venv/bin/python benchmarks/three_arm_v1/admission.py \
  --output runs/three-arm-v1/admission \
  --regression-receipt runs/three-arm-v1/regression-receipt.json \
  --plugin-dir tools/mlir_dispatch/build-issue6 \
  --mlir-opt /tmp/issue6-llvm-23.1.1/bin/mlir-opt
.venv/bin/python benchmarks/three_arm_v1/driver.py prepare \
  --run-dir runs/three-arm-v1/formal \
  --semantic-gate runs/three-arm-v1/admission/gate.json \
  --plan-map runs/three-arm-v1/admission/plan-map.json \
  --stage-binary rust/runtime/target/release/stage-c-benchmark
```

Before `measure`, obtain all agent stop acknowledgements and independent gate
review. Execute on the real host, with visible host processes (not a restricted
PID namespace). No build/test/compiler/profile overlaps the formal window.

```sh
.venv/bin/python benchmarks/three_arm_v1/driver.py measure \
  --run-dir runs/three-arm-v1/formal --deadline-seconds 1200
.venv/bin/python benchmarks/three_arm_v1/summarize.py runs/three-arm-v1/formal \
  --output runs/three-arm-v1/summary.json
```

A failed/partial window is permanent evidence, not permission to retry. A
bounded performance benefit is not default adoption. Whole-process RSS and
single-sample counters have the limits explicitly described in the protocol;
no batch-only memory or unmeasured phase decomposition is inferred.
