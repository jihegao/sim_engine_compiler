# Integrated compiler/runtime baseline

This is the first slice of issues #4/#6: strict canonical work validation plus a
new baseline after MC, O5, MLIR and cache v3 integration. It does not implement
Business/Core IR persistence or candidate-instance dispatch.

Run the conformance tests before measuring. Build current-checkout LLVM/MLIR
23.1.1 plugins and commit source changes, then:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/integrated/run_benchmark.py \
  --output benchmarks/integrated/results/macos-arm64-20260925 \
  --plugin-dir tools/mlir_dispatch/build-make \
  --mlir-opt /opt/homebrew/opt/llvm/bin/mlir-opt \
  --samples 32 --threads 1,2,4,8 --repeats 3
```

The runner refuses tracked source changes, records commit/tree/toolchain/input
and executable/plugin hashes, and executes measurements sequentially. The two
MLIR three-arm experiments compare full results for seeds 0/1/7 for minute and
O5 profiles independently. Strong scaling uses O5 with index off/on, full/summary,
32 samples (including duplicate seeds), and forward/reverse configuration order.
Each invocation warms one batch, measures one repeat, and records initialization,
execution, serialization, output, total batch time and process peak RSS on macOS.
Sample hashes must agree across every thread count and repeat for each arm.
Index on/off full-tree parity is enforced separately by the three-arm experiment.

`batch_execution_ns` includes preparation, per-sample state initialization and
Rayon setup/execution. `single_sample_execution_ns` excludes state initialization.
`end_to_end_batch_ns` includes Plan file reading, validation, fingerprinting,
execution, serialization and file writing; it excludes canonical compilation and
process startup. RSS covers the whole invocation, including warmup. OS scheduling,
heterogeneous cores, uncontrolled frequency and background load limit hardware
scaling conclusions. This is one host, not an AMD128 reproduction.

`cache-v3.json` measures canonical-input AOT miss/hit, including summary execution
as separate arms. It excludes Project export/Adapter and is **not** a pre-Adapter
Project-cache or Rust Adapter measurement. Optional `binding.json` records MC
binding calls and cache stages separately; if native loading is unavailable,
`identity.json` records that boundary as unmeasured. Allocation counts and NUMA
experiments are not measured here.

Historical source snapshots and golden results are not overwritten. See the
result directory's `REPORT.md` for measured values, acceptance and limitations.
