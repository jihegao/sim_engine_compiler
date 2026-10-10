# Frozen source and implementation audit

Read-only independent audit on AMD128, 2026-09-27. Upstream repository
`/home/g/Models/spare_mvp` was clean at
`0e709bdcc2d692d9cfed49b9037c76ef71aefe33`. The official no-database exporter
`benchmarks/batch_preparation/export_spare_mvp_case.py` reproduced the checked-in
J35 canonical file and manifest byte-for-byte (both `cmp` exit 0).

| Identity | Value |
|---|---|
| Project | `exports/project-case-large.json` |
| Project SHA256 | `dd37321d012145b3b1554f23f58bca4d70843bfd49cc22233d4969be2f247569` |
| Project schema SHA256 | `ac33186709dce50a252f2153273cab4be5f6f8e57dcd2b8f515eb08e4d3f4b4c` |
| Input schema SHA256 | `bd8d6acca8e4fb678bf0b536d257fae41811f44e3c841b13cabdc32c2fe3f694` |
| Adapter Git blob | `f78ea525ed8a2e631204bea1914e368befcae8b1` |
| Canonical file SHA256 | `ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793` |
| Canonical semantic digest | `faf7c801351fd1cd3817fe3f03fe2b7e95056a7c1d9733e5863b291fddc2a689` |

The last two hashes use different encodings; Plan.source_inputs_sha256 uses
the semantic digest. The input contains 8 J35 aircraft, 424 components,
13 support activities, two resource nodes and a 61,920-minute horizon.
Source remains under `benchmarks/batch_preparation/results/amd128-j35-20260926/source`;
new generated runs remain separate. Runtime headless override disables frames
only, as recorded in the historical source manifest. No database was read/copied.

Three arms reuse `run_batch_with_dispatch -> PreparedBatchPlan::from_plan_with_fingerprint
-> run_prepared_batch`. All samples share immutable preparation, and mutable
Runtime/RunState remains independent. Unindexed scan sorts all waiting jobs;
indexed scan retains that outer scan and reuses blocked guard results;
candidates uses reverse-dependency wakeups and BTreeSet ordering, with v2
index validation. Full-mode replay is additional work and is reported.
`mlir_resource_dispatch_benchmark` is not this three-arm experiment: it does
not enable candidate dispatch. The existing stage-c benchmark does.

The CLI cannot aggregate per-sample RuntimeProfile across batches. This slice
uses separate single-sample profiles, not invented batch totals. Stage-c
bundles batch preparation, initialization and execution; separate single-sample
initialization is not batch initialization. These limits are retained in the
protocol and final report rather than inferred by subtracting other timings.
