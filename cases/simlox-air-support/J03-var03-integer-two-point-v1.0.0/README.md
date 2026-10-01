# J03.var03 integer two-point mission count

This bounded case derives from accepted `J02.var01@1.0.0` count-two seed 01.
It replaces one `IntegerDistributions` `COUNTD/<DETERM>/PARAM1=2/PFAC=1`
row with two rows of the same distribution ID: `<DETERM>/PARAM1=0`
and `<DETERM>/PARAM1=2`, each with `PFAC=0.5`. It retains six deployed
aircraft, `RANDOM`, `IQTYD=COUNTD`, `IPER=0`, `EQUIDIST`, hour-8 mission
start, two-aircraft formations, a two-hour mission, and hour-36 horizon.
Seeds 02–32 change only `Control.RSEED`. `build.py --check` verifies
the accepted parent fingerprint and exact source diff.

Thirty-two excluded diagnostic runs fixed the observation sequence. Thirty-two
fresh accepted session-0 SSH runs reproduced counts 0 and 2, with frequencies
0:15 and 2:17, sample mean 1.0625 and sample variance
1.028225806451613. Each two-count run activates and completes two
simultaneous two-aircraft formations at hours 7–10; zero-count runs
activate none. Six aircraft suffice in every accepted run. Reports have
72 aligned System/Stock bins, four aircraft flight hours per completed
mission, no stock demand and six aircraft ready at horizon.

The runner uses authenticated session-0 SSH, the host-wide Issue #18 mutex,
exact source and installed manual/dictionary/executable hashes, and a
start-identity guard for GUI PID 13340. Every accepted run records four
native steps and seals 11 raw files. The ignored local `runs/` directory
holds the raw evidence. `validate.py RUN_DIRECTORY SEED` replays one run
without SIMLOX, and `validate_panel.py` checks the 32 accepted runs.
`evidence-index.json` records run IDs and SHA-256 seals. On a clean
checkout without existing runs, run a seed with its hash from
`panel-diff.json`; the runner requires
`j03-var03-seedNN-accepted-20261001-01`.

Independent read-only replay, without importing author validators, passed
45,381/45,381 checks including all 352 raw seals and direct MTMF/STMF/STACC
report checks. It excluded all 32 diagnostic probes. The installed
dictionary and manual are SHA-256 pinned in `contract.json`; the manual
discusses integer distributions and PFAC mixture factors on pages 541–543.

This fixed sample establishes native behavior for these inputs and seeds.
It does not establish the population 50/50 weights, stream independence,
unobserved behavior, GUI visual content or cross-engine parity.
