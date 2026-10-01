# G05.var05 overlapping passive switches: bounded CLI sign-off

**Decision:** accept and publish the fixed-seed short/long four-branch pair for observed overlapping activations and system-level switch-state accounting. GUI and cross-engine equivalence were not observed.

## Source and native gates

- Accepted direct parent: `G05-passive-threshold-v1.0.0/two-input.json`, SHA-256 `f09cc7e9d8f1843148b537125760dc02adfb51bdc1c634e5e03e138af19bb8c4`, run `g05-nbreq-two-v100-ssh-20261002-01`. Short source SHA-256 `8739ac36a0bed2109e4c8c8804b536d618ce6cb8a716f4c8c2e36923a2cdf873`; long source SHA-256 `9616f54907ff35ddab1c33db67e0f1db45d151f5d2a27cb101e0da4f6f02f39a`; exact-diff SHA-256 `58854db97678aeae1ed7a8e640e0595bdde89f2c31b4d4d8c90abae6ca337ff3`.
- Both arms add nonfailing POS-D to the accepted three-branch parent using `MaterielPosition`, `MaterielStructure`, `MaterielOperationalModes` and `RBDParallelStructure`, with descriptive updates. Within the four-branch pair, the only behavioral delta is `RBDParallel.TSWOV 0.5→9.0 h`; `ProblemDescription.PDESC` also differs. `NBOP=NBREQ=2`, priorities B/A/C/D, B/A failure modes, seed, mission, direct CM and report windows are identical.
- SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The manual's pp197–200 and 455–458 define this passive RBD configuration; native results below determine the accepted behavior.
- Run IDs `g05-overlap-short-v101-ssh-20261002-01` and `g05-overlap-long-v101-ssh-20261002-01`. Each used session-0 SSH with `sshd.exe` ancestor, host mutex `Global\SimloxIssue18NativeQueue`, preserved GUI PID 13340/session 1/start identity, unique run directory and five completed guarded steps. Import/export roundtrips exactly match 23 authored row-containing tables; converter errors are zero; SXI/SXO/log/report are nonempty. The evidence index seals 12 raw files per accepted arm, plus pins the prior unpublished four-hour diagnostic raw runs.

## Observed timeline and ledgers

| Arm | B→C | A→D | Overlap | System `NSYSW` | System `NSYMO` |
| --- | --- | --- | ---: | ---: | ---: |
| Short, 0.5 h | 8.62763–9.12763 | 11.5942–12.0942 | 0 h | 1 h | 25 h |
| Long, 9 h | 8.62763–17.6276 | 16.7498–25.7498 | about 0.878 h | about 17.1222 h | about 8.8778 h |

The long arm's A failure and A→D start occur while B→C remains unfinished; both switches later complete. Its 72 aligned half-hour `SystemResults` bins keep `NSYSW` occupied through the overlap, so the integrated system state matches the union of activation intervals (`25.7498−8.62763≈17.1222 h`), not their 18 task-hours. The short arm has two disjoint half-hour intervals. Both B and A failures are noncritical, both missions succeed h34, two deferred half-hour direct CM tasks finish h34.5, and the h36 system is ready. All 72 `StockTotalResults` bins show zero demand, backorder and movement. Author raw replay passes 51/51 (SHA-256 `265b17b14a5f0fc06f69ed6866f2df57c05b1f07a98aeb4da7667f69c775495f`); independent read-only replay passes 3,453/3,453 with GO (checker SHA-256 `f41cdc338e8180bd15d6d1b959a38b07b87300a7a7105a6fe3ea1049f7d0271a`, verdict SHA-256 `87447a0f1614cc97f63fb786502ac687f7f52de09284c18b0541ac269cd3a9f7`).

## Limits and prior diagnostic

The second A failure is h11.5942 in the short arm and h16.7498 in the long arm; the pair does not establish a universal rule for when failure clocks pause or reschedule. Only one seed, one repetition, two durations and this B/A/C/D configuration were tested. The earlier v1.0.0 0.5/4-hour pair had two disjoint switches in both arms and remains an unpublished diagnostic, with raw closure hashes and logs pinned in the evidence index. This publication does not claim every overlapping-switch scheduling outcome, unavailable preferred standby G05.var04, GUI RBD rendering or cross-engine parity.
