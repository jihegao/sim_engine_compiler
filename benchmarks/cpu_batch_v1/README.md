# F35 CPU batch baseline v1

This is a bounded offline experiment for Issue #6, based directly on runtime
`595cb5eee9987324b19a8c3566f201f937e05f15`. It changes no engine, compiler,
RNG, dispatch, or default path. Read [PROTOCOL.md](PROTOCOL.md) before running.
The protocol, semantic gate, and measurement are separate stages. CI runs
synthetic harness controls, never the formal performance window.

The two measured boundaries are the existing Rust `stage-c-benchmark` executable
and public Python `sim_engine_compiler.run_batch`. Their timings are not
interchangeable. Default aircraft batch already shares preparation within each
call; this is not a candidate-optimization or persistent-handle experiment.

## Preparation and admission

Use an isolated checkout and Python 3.12 virtual environment. Build before any
formal window:

```sh
RUSTUP_TOOLCHAIN=1.90.0 uv pip install --python .venv/bin/python -e '.[test]'
cargo +1.90.0 build --locked --release --manifest-path rust/runtime/Cargo.toml --bin stage-c-benchmark --bin sim-engine-runtime
PYTHONPATH=src .venv/bin/python -m unittest tests.conformance.test_cpu_batch_baseline -v
```

Compile the frozen canonical fixture with the existing `scripts/compile_ir.py`,
select `--semantic-profile event-time-v2`, and persist all layers with
`--artifacts-dir`. Compilation is outside this experiment's measured stages.
`driver.py freeze --help` lists the explicit Plan, lineage, compiler command,
install-provenance, and output-root arguments. Freeze creates a **new** run
directory and refuses source/profile/input mismatches. Its manifest binds
the protocol, environment, executable/module bytes, source, Plan and ordered
56-cell schedule. Digests prove local consistency, not independent authorship
or authenticity of a self-entered build command.

```sh
PYTHONPATH=src .venv/bin/python benchmarks/cpu_batch_v1/driver.py semantic-gate --run-dir FROZEN_RUN_DIRECTORY
```

The gate stores actual reference/CLI/PyO3 results. Existing F35 Python-reference
floating tolerances are reported separately from strict equality. O5/profile,
observation and worker comparisons are exact after only their named contract
normalizations. Failure keeps evidence and forbids performance admission; do
not edit the oracle or relax comparison to produce timings.

## One controlled window

Only the coordinator starts the formal window, after confirming all local
agent tests/builds/benchmarks have stopped. Retain full preflight process
inventory, live load snapshots and ongoing process monitoring. Normal OS,
desktop, remote-access and network services are not stopped; describe the
window as controlled/best-effort, not as proof of zero background load.
Any known competing CPU-heavy job closes the window. Never stop unrelated
processes to manufacture a clean result.

```sh
PYTHONPATH=src .venv/bin/python benchmarks/cpu_batch_v1/driver.py measure --run-dir FROZEN_RUN_DIRECTORY --deadline-seconds 1200
PYTHONPATH=src .venv/bin/python benchmarks/cpu_batch_v1/driver.py summarize --run-dir FROZEN_RUN_DIRECTORY
```

The sole window cannot resume or overwrite. An incomplete matrix stays
incomplete; no second window or changed workload is authorized by this tool.
Each process is pinned to CPUs 0–7, performs one warmup and one primary call,
and is wrapped by GNU time. Rust also performs its existing single-sample and
second end-to-end diagnostics. PyO3 retains warmup and measured result trees
for comparison: its whole-process RSS includes both plus proof/encoding work.
Neither RSS nor elapsed process time is a batch-only allocation/startup metric.

Only N64 paired repeats yield within-backend/observation worker scaling.
N1/N8 probes remain separate. Missing stage splits stay unmeasured; do not
subtract different boundaries to invent them. Three repeated identical seed
sets describe timing spread, not scientific outcome uncertainty.

Keep raw evidence and hashes, including a failed admission or partial window.
No result here closes Issue #6, establishes a general adoption decision, or
supports a cross-hardware SIMLOX ratio. No merge is authorized.
