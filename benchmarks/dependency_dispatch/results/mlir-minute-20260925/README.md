# MLIR resource dispatch pilot: F35 real-case evidence

- Input file SHA-256: `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`
- Canonical source input SHA-256: `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`
- Upstream spare_mvp revision: `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`
- Semantic plan fingerprint: `f3a055330fe3c03bb9d47c745e12fdaeae11ac29ff355c1751534163fc7da256`
- LLVM/MLIR: `23.1.1`; Rust: `rustc 1.90.0 (1159e78c4 2025-09-14)`
- Seeds/runtime repeats/compiler repeats: `[0, 1, 7]` / `3` / `3`; complete `RunResult` JSON trees were compared exactly.
- MLIR emitted `898` candidate rules.

| Arm | Compile wall (s) | Candidate visits | Guard evaluations | Cache hits | Median execution (ms) | Median runtime end-to-end (ms) | Compile + load + all runtime samples (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 现有编译链 | 0.1285 | 1005081 | 1005081 | 0 | 208.994 | 212.087 | 2.0593 |
| MLIR 验证，业务 pass 关闭 | 0.2281 | 1005081 | 1005081 | 0 | 206.916 | 210.060 | 2.1327 |
| MLIR 资源索引 pass 开启 | 0.2506 | 1005081 | 40737 | 964344 | 180.176 | 189.363 | 1.9729 |

Exact full-result parity: **True** across all arms and seeds.

The runtime still visits waiting jobs in existing priority/time/job-ID order to preserve event placement. `guard evaluations` counts full dynamic spare, route, and capacity checks; cache hits replay the original per-minute capacity delay event where required. The measurement does not claim fewer outer waiting-list visits.

`Compile + load + all runtime samples` includes one compile, one plan read/parse/validation, and the measured end-to-end runtime of every seed/repeat. The one-time MLIR plugin and Rust binary builds are excluded. Detailed per-run counters and nanosecond phase profiles are in `benchmark.json`; generated plans and compiler timing metadata are adjacent files.

Decision: guard evaluations fell by 95.95%, and compile + load + sample total cost fell by 4.20% for this workload. This is F35-specific evidence, not a general scaling guarantee.