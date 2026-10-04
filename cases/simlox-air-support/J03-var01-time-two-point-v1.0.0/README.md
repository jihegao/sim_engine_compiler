# J03.var01 two-point empirical preparation table

This bounded case derives from accepted `J01.var01@1.0.0` input. It
replaces the single `TimeDistributions` `PREP-DET/<DETERM>/PARAM1=0.5/
PFAC=1` row with two `PREP-DET/<DETERM>` rows at 0.25 and 0.75 hour,
each with `PFAC=0.5`. It retains the mandatory 0.5-hour
`MissionPreparation.DURN`, `DURND=PREP-DET`, one aircraft, scheduled
hour-8 start, one-hour notice, two-hour mission and hour-36 horizon.
Seeds 02–32 change only `Control.RSEED`. `build.py --check` verifies
the accepted parent fingerprint and exact source diff.

Thirty-two excluded diagnostic runs fixed the observation sequence.
Thirty-two fresh accepted session-0 SSH runs reproduced 0.25-hour
preparation in 15 seeds and 0.75-hour preparation in 17. The sample
mean is 0.515625 hour and sample variance is 0.06426411290322581.
Preparation starts at hour 7; both durations finish before the
scheduled hour-8 mission launch. Every accepted mission succeeds and
completes at hour 10. Each report has 72 aligned System/Stock bins,
the matching preparation integral, two aircraft flight hours, no
stock demand and the aircraft ready at horizon.

The runner uses authenticated session-0 SSH, the host-wide Issue #18
mutex, exact source and installed manual/dictionary/executable hashes,
and a start-identity guard for GUI PID 13340. Each run records four
native steps and seals 11 raw files. The ignored local `runs/`
directory holds raw evidence. `validate.py RUN_DIRECTORY SEED` replays
one run without SIMLOX, and `validate_panel.py` checks the 32 accepted
runs. `evidence-index.json` records run IDs and SHA-256 seals. On a
clean checkout without existing runs, use the matching seed hash from
`panel-diff.json`; the runner requires
`j03-var01-seedNN-accepted-20261001-01`.

The installed manual explains deterministic support points and PFAC
mixtures on pages 541–545. The proprietary manual and database
dictionary are SHA-256 pinned in `contract.json` and are not included.

This fixed sample establishes native behavior for these inputs and
seeds. It does not establish population 50/50 weights, stream
independence, unobserved behavior, GUI visual content or cross-engine
parity.
