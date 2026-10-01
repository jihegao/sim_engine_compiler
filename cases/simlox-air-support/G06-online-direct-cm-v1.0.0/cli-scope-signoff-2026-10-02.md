# G06.var01 ONLM direct-CM timing: bounded CLI sign-off

**Decision:** accept and publish the one fixed-seed `ONLM=Y/N` continuous-mission direct-CM contrast. The result concerns native timing of two direct system repair tasks in one passive parallel RBD. GUI view and cross-engine parity were not observed.

## Source and guarded native gates

- Accepted `ONLM=Y` parent: `G05-unavailable-standby-v1.0.3/unavailable-input.json`, SHA-256 `b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d`, run `g05-unavailable-v103-ssh-20261002-01`. `ONLM=N` child SHA-256 `1bb1a9b9f9e583f2dd087b4e99f179f2194fbb1af92051a56ff14eafa3dea7e3`, run `g06-deferred-v100-ssh-20261002-01`. Exact two-table diff SHA-256 `2f3dd160cbc1129391e39c094c195d4170d1936397b68ec161d53958bff0a371`: only `RBDParallel.ONLM Y→N` and `ProblemDescription.PDESC`. Mission `MPAT=CONTINUOUS`, `TFOUT/TFRET=null`, seed, 26-hour schedule, B/A/C priorities, `NBOP=NBREQ=1`, `TSWOV=0.5`, failure modes, B CMT40, A CMT0.5, stock and all other rows match.
- Installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; table dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Manual pp198–199 and 455–457 describe online repair for continuous/extendable missions and deferral under `ONLM=N`.
- Both runs used session-0 SSH with `sshd.exe` ancestor, `Global\SimloxIssue18NativeQueue` mutex, immutable run directories and preserved GUI PID13340/session1/start identity. Each completed import/export/calc/report/roundtrip, had zero converter errors and exactly roundtripped 23 populated authored tables. The evidence index seals 12 raw files per arm. Author raw replay passes 34/34 (SHA-256 `01c7042abb47133779b44c66a17b4e30ae57a1aec0b8c6799ade3b3afa7f845e`); independent replay passes 1,732/1,732 GO (checker SHA-256 `bd9046503b1ae765961bb5afcdfaadf67fe8420fa36504dff07d235ad6c30b42`, verdict SHA-256 `412ea80182e3bef3b0618706169a0e997c3d6ddb770b12603e6cf4bb9f61a346`).

## Observed repair contrast

| Event | `ONLM=Y` | `ONLM=N` |
| --- | ---: | ---: |
| B fails; B→A starts | h8.94145 | h8.94145 |
| B→A completes | h9.44145 | h9.44145 |
| A fails; A→C starts | h17.5636 | h17.5636 |
| A→C completes | h18.0636 | h18.0636 |
| B 40-hour CM starts | h8.94145 | h34 |
| A half-hour CM starts | h17.5636 | h34 |
| A CM completes | h18.0636 | h34.5 |

Both mission logs record success and completion at h34. Both have 72 aligned half-hour System and Stock bins, `NSYSW=1` system-hour, `NSYMO=25` hours, `NFAIL=2`, `NREPT=1`, terminal `NSYRP=1` and `NSYRY=0`, and zero stock movement. The System tables are identical except that `NREPT` shifts from [18,18.5) in Y to [34.5,35) in N; all Stock bins and ResultSummary fields match. In these continuous runs, ResultSummary `MTMF=1` and `STMF≈0.961538`, while fixed-mission fields `MSTF=MSUF=0` despite the separate mission-success event. Those observations remain distinct.

## Limits

This pair isolates `ONLM` source-wise for one direct system CM configuration and one seed. B's forced 40-hour CM remains unfinished in both arms at horizon36. No item or physical replacement, stock issue, resource demand, non-base location, shortage, fixed/extendable contrast or whole-parallel-block failure was exercised. The case does not establish all G06 repair modes or a population timing rule.
