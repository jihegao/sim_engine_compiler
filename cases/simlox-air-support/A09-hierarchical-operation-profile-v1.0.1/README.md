# A09 nested profile, v1.0.1 bounded publication

The [later bounded sign-off](cli-scope-signoff-2026-09-29.md) publishes the
tested four-wave CLI recipe after A02 parent acceptance and separate read-only
replay. The original `1.0.1-candidate` contract and run labels remain frozen.
This candidate **passed one source-bound native SIMLOX CLI run** on 4700-3.
The [2026-09-29 acceptance record](native-acceptance-2026-09-29.md) pins the
run ID, original Windows artifacts, hashes, observed waves, and evidence
limits. A partial [GUI review](gui-review-2026-09-29.md) of this A09 v1.0.1
model has been performed; its original record says `not_published` because
it predates the later sign-off. The
[v1.0.0 nested source](../A09-hierarchical-operation-profile/native-nested.json)
and its failed native run remain unchanged. The [flat v1.0.0 source](../A09-hierarchical-operation-profile/native-flat.json)
passed the isolated CLI contract in run `a09-flat-nested-20260929-02-flat`;
the nested source failed that contract in run `a09-flat-nested-20260929-02-nested`.
The [contract](contract.json) records each run's original Windows path,
source SHA-256, `model.log` SHA-256 and validation SHA-256, plus the flat
control's raw report SHA-256. These two outcomes
are tied to v1.0.0 source commit `6beb791` and its retained raw run directories;
the v1.0.0 outcomes do not establish GUI review or full A09 method coverage.
A02 is the frozen parent. Its bounded repeated-wave CLI behavior was later
published in the [A02 sign-off](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md).

The only model change is the root `OperationProfile` row
`BASIC-SCHEDULE → A09-DAILY-TWO-WAVE`, `STIM=0`, `IQTY=2`:
`IPER=24 → 48` hours. The child rows remain at relative `STIM=8` and `20`.
The [builder](build.py) checks the three source SHA-256 fingerprints and
rejects any other model change. Run `python3.12 build.py` to check the checked
candidate; `--write` is only for reproducing its original bytes.

In the v1.0.0 native run, both inputs imported, roundtripped, and converted
with zero errors. The nested input ordered missions at hours **7, 19, 19, 31**;
three started at **8, 20, 32** and the extra hour-20 mission was cancelled at
printed hour **20.3333**. The run produced no hour-43 notification. The raw
run path and `model.log`/validation SHA-256 are in [the contract](contract.json).
These observations are compatible with two root instances separated by 12
hours. `IPER/IQTY` is one possible explanation, not an established SIMLOX
rule. The repository's manual mapping confirms the nested reference and hour
units but does not specify this quantity/period formula. The local v1.0.0
expander assumed separation equal to `IPER`; that assumption failed this native
run.

The `IPER=48` input produced notifications at 7/19/31/43, starts at
8/20/32/44, and completions at 10/22/34/46 in the new native CLI run, with
no cancellation. Its `model.log` and `report-raw.json` are byte-identical to
the passed flat control. This one run does not establish a general
`IPER/IQTY` expansion formula. The version-specific [SSH CLI runner](run_native_ssh.ps1)
and [native validator](validate_native_cli.py) generated and checked that run.
They bind the source, executable, Python parser, SSH session, existing GUI
PID/session/start time, four native command steps, raw file closure, 4 complete
mission lifecycles and 96 half-hour result intervals. A failed run remains in
its own directory. `-AllowExistingGui` permits one active interactive SIMLOX
GUI to coexist, while the new work still runs as session-0 CLI; it does not
count as GUI review. The v1.0.0 pair runner and validator remain pinned to the
old inputs.

The result and event checks are pinned to the passed v1.0.0 flat raw run:
`SystemResults.STACC` matches its 8 flight hours in all 96 intervals;
`ResultSummary` checks all 11 observed fields, including
`MTMF/RSMTMF/RSMSTF/RSMSUF/STMF/RSSTMF`. The validator also requires the
flat-control `ready` (8), `systems_ready` (5), and `soon_ready` (4) event
counts, times, and aircraft/unit identities. These are A09 acceptance
expectations, not a general interpretation of the SIMLOX field names.

The source-bound snapshot included this directory, the unchanged A02 and
v1.0.0 A09 sources, and the shared `tools/validate_native.py` and
`tools/native_binding.py`. The authenticated SSH PowerShell run used the
following command shape with run ID `a09-v101-20260929-01`:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$repo\cases\simlox-air-support\A09-hierarchical-operation-profile-v1.0.1\run_native_ssh.ps1" -RunId "a09-v101-20260929-01" -AllowExistingGui
```

`$repo` was the snapshot's absolute root. The runner refuses a reused run ID
and a disconnected GUI session. Import, roundtrip, conversion, events,
cancellation, result intervals, and an independent read-only raw replay passed
for this run. The coexisting GUI PID/session remained stable during the CLI
steps. A subsequent partial GUI review is recorded separately. The dated
sign-off publishes only this tested CLI behavior; full A09 method coverage,
unobserved GUI behavior, and cross-engine equivalence remain unverified.
