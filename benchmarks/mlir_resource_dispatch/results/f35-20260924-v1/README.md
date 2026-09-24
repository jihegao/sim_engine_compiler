# MLIR resource dispatch pilot: F35 real-case evidence

- Input file SHA-256: `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`
- Canonical source input SHA-256: `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`
- Upstream spare_mvp revision: `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`
- Semantic plan fingerprint: `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`
- LLVM/MLIR: `23.1.1`; Rust: `rustc 1.90.0 (1159e78c4 2025-09-14)`
- Seeds/runtime repeats/compiler repeats: `[0, 1, 7]` / `3` / `3`; complete `RunResult` JSON trees were compared exactly.
- MLIR emitted `852` candidate rules.

| Arm | Compile wall (s) | Candidate visits | Guard evaluations | Cache hits | Median execution (ms) | Median runtime end-to-end (ms) | Compile + load + all runtime samples (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 现有编译链 | 0.0563 | 1005081 | 1005081 | 0 | 201.846 | 204.954 | 1.9255 |
| MLIR 验证，业务 pass 关闭 | 0.1202 | 1005081 | 1005081 | 0 | 203.315 | 206.407 | 1.9852 |
| MLIR 资源索引 pass 开启 | 0.1474 | 1005081 | 42936 | 962145 | 177.450 | 185.868 | 1.8435 |

Exact full-result parity: **True** across all arms and seeds.

The runtime still visits waiting jobs in existing priority/time/job-ID order to preserve event placement. `guard evaluations` counts full dynamic spare, route, and capacity checks; cache hits replay the original per-minute capacity delay event where required. The measurement does not claim fewer outer waiting-list visits.

`Compile + load + all runtime samples` includes one compile, one plan read/parse/validation, and the measured end-to-end runtime of every seed/repeat. The one-time MLIR plugin and Rust binary builds are excluded. Detailed per-run counters and nanosecond phase profiles are in `benchmark.json`; generated plans and compiler timing metadata are adjacent files.

Decision: guard evaluations fell by 95.73%, and compile + load + sample total cost fell by 4.26% for this workload. This is F35-specific evidence, not a general scaling guarantee.