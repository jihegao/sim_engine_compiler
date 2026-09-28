# A09 — two days of two mission waves, flat and hierarchical candidates

These are **local candidate inputs only**. Neither input has been imported,
roundtripped, calculated or reviewed in native SIMLOX. The nested time expansion
is a hypothesis from the [A09 manual mapping](../manual-coverage-v2.json), not
a verified SIMLOX rule. The case does not complete A09's full boundary matrix
and is not published.

The parent is frozen [A02@1.0.0](../A02-single-aircraft-repeated-missions/native-input.json)
at SHA-256 `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
Both candidates retain its one ready aircraft, two-hour mission, one-hour
notice, inert mechanisms, `Operations.PRID=BASIC-SCHEDULE`, and half-hour
collection interval. They extend the horizon and collection window from 36 to
48 hours and use a case-specific `ProblemDescription.PDESC`.

| Candidate | `OperationProfile` construction | Hypothesized start hours |
| --- | --- | --- |
| [flat](native-flat.json) | Four direct `BASIC-SCHEDULE → BASIC-MISSION` scheduled rows | 8, 20, 32, 44 |
| [nested](native-nested.json) | Root `BASIC-SCHEDULE → A09-DAILY-TWO-WAVE`, `STIM=0`, `IQTY=2`, `IPER=24`; child profile has relative 8 and 20 hour mission rows | 8, 20, 32, 44 |

The root row's `ITYPE=SCHEDULED` and `DTIM=null`, the child's relative `STIM`,
and `IQTY=2/IPER=24` expansion **require native import, roundtrip, simulation
and GUI validation**. A conversion error or different expansion is a failed
candidate and must be retained as evidence, not silently repaired in place.
Manual heading `OperationalProfile` maps to the single native table
`OperationProfile`; no alias table is generated. Multiple rows may share a
`PRID`, so validation retains row multiplicity.

The [flat parent diff](parent-diff-flat.json) and
[nested parent diff](parent-diff-nested.json) each change exactly `Control`,
`OperationProfile`, `ProblemDescription`, `ResultCollection`. The
[variant diff](variant-diff.json) changes only `OperationProfile`. The
[contract](contract.json) holds the hand timeline: notifications 7/19/31/43,
starts 8/20/32/44, completions 10/22/34/46 hours, four sorties and 96
half-hour result intervals. These are targets, not observed native outcomes.

Local reproduction and checks, using Python 3.12 or newer:

```bash
python3.12 cases/simlox-air-support/A09-hierarchical-operation-profile/build.py --check
python3.12 cases/simlox-air-support/A09-hierarchical-operation-profile/validate.py
uv run --no-project --python 3.12 --with pytest pytest -q tests/conformance/test_simlox_a09.py
```

The first native sprint should run the flat input, then the nested input,
serially in new source-bound run directories. Compare raw event identities and
times, not only aggregates or generated ordinals. Inspect the root and child
curves and four waves in the native GUI. A02's own GUI/publication gate remains
separate. Catalog variants for simultaneous `IQTY>1/IPER=0`, repeated-key
equivalence, illegal Random/Regenerative children, and native missing/cycle
conversion are still untested; this baseline cannot be marked full A09
acceptance.

The prepared [SSH CLI runner](run_native_ssh.ps1) accepts one fresh `RunId` and
creates `<RunId>-flat` followed by `<RunId>-nested` under ignored `runs/`. It
holds the host-wide Issue #18 mutex for both candidates. If the existing GUI
must coexist, pass `-AllowExistingGui`; the runner requires one active Console
or RDP session and rechecks its PID, session and process start before and after
every native command. A failed flat run stops before nested. Each completed
run keeps source/runner/parser/executable hashes, command exit records, raw
hash closure and a [read-only behavioral validation](validate_native_cli.py).
The validator checks all four event lifecycles, identity continuity, 96
half-hour intervals and zero mechanism indicators. It permits different
native-generated mission ordinals if each wave has one consistent identity.
This runner and validator have local negative tests only; they have not been
executed on `4700-3`.

From an authenticated session-0 SSH PowerShell shell, after placing the A09
directory, A02 `native-input.json`, `tools/validate_native.py`, and
`tools/native_binding.py` in their repository-relative positions, the planned
single invocation is:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$repo\cases\simlox-air-support\A09-hierarchical-operation-profile\run_native_ssh.ps1" -RunId "a09-unique-run-id" -AllowExistingGui
```

`$repo` must name the fresh isolated checkout root. The command is a prepared
handoff, not an execution record. A failure leaves the raw candidate run in
place for diagnosis; use a new run ID after any source revision.
