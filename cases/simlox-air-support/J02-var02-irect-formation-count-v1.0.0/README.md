# J02.var02 integer rectangular mission count

This package tests the catalog's `J02.var02` `<IRECT>` count option
against accepted `A03@1.0.1`, the two-aircraft formation model. The
source keeps the two-hour mission, hour-8 start, one-hour notice and
hour-36 horizon. `OperationProfile.ITYPE` changes to `RANDOM` because
the native `IQTYD` field is invalid under `SCHEDULED`; `IQTYD=COUNT03`
uses one `IntegerDistributions` row with `PFAC=1`, `<IRECT>`, lower 0 and
upper 3. `IPER=0` and `IDISP=EQUIDIST` keep all realized missions at
hour 8. Deployment increases from two to six aircraft so up to three
simultaneous two-aircraft formations can launch. `IQTY=1` remains in
the input but native warning #211 states that it is ignored when the
user-defined `IQTYD` is present. Seeds 02–32 differ from seed 01 only
in `Control.RSEED`. Run `build.py --check` to verify all source inputs
and the exact parent diff.

The installed database dictionary lists `<IRECT>` for integer
distributions and allows nonnegative parameters. The installed manual
pp. 541–543 describes integer distributions and lower/upper limits;
pp. 271–274 describe random initiation and zero `IPER`. Proprietary
sources are SHA-256 pinned in `contract.json` and are not included.

Run each seed through `run_native_ssh.ps1` in an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The
runner checks GUI PID 13340 and its start identity, native executable,
source hashes and the host-wide Issue #18 mutex. It seals partial raw
evidence after a failed step. `validate.py RUN_DIRECTORY SEED` replays
one run without SIMLOX; `validate_panel.py` checks the 32 accepted
runs. Ignored local `runs/` folders and raw SHA-256 seals are indexed
in `evidence-index.json`.

The 32 excluded diagnostic seeds produced counts 0, 1, 2 and 3 with
frequencies 8, 7, 9 and 8. A zero count generated no activated or
started mission, although a profile sentinel appeared in the log.
Positive counts produced that many simultaneous successful missions,
each with two distinct aircraft. Fresh accepted IDs must reproduce
the frozen count sequence. These fixed-seed observations cannot prove
the population law, endpoint weights, independence, other count
ranges, shortage behavior, GUI-only behavior or cross-engine parity.
