# C09.var02 v1.0.2 reproduction guide

**Status: prelaunch, not published.** This guide is outside the frozen 256-record prelaunch manifest. It does not approve a native run. The central `../publication-index-v1.json` is the authority for any later publication status. The frozen [contract](contract.json) and [prelaunch manifest](prelaunch-manifest.json) define the exact planned source bytes, hypotheses, and two reserved run IDs. At this guide's creation, neither v1.0.2 SSH preflight nor native execution has occurred.

## Read-only static replay

Use the bundled Python runtime from this package directory. These commands verify the generated input bytes without rewriting them, all accepted local and published Git source pins, 117 accepted raw seals and nine invocation/closure pairs, installed dependencies, the accepted C09 parent report's 5,210 cells, and the adversarial checks. A passing static replay is not evidence that either new native arm succeeded.

```powershell
Set-Location 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.2'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -X utf8 .\build.py
& $python -X utf8 .\verify_sources.py
& $python -X utf8 .\self_check.py
& $python -X utf8 .\make_prelaunch_manifest.py
```

Expected frozen-manifest identity: SHA-256 `0789c128a656b0d405932ec053dc80853ecc8f7dd692f9b4eb3041e80ee8ce4a`, 87,539 bytes, 256 source records. `verify_sources.py` must report 78 accepted source disk/Git pairs, 117 raw seals, nine closures, nine invocations, three installed pins, and three excluded v1.0.0 pins and 20 excluded v1.0.1 pins. `self_check.py` must report 5,210 parent report cells and 24 adversarial rejections. A changed count or hash stops the prelaunch gate; it is not repaired by editing a frozen source.

| Frozen v1.0.2 file | SHA-256 |
|---|---|
| `contract.json` | `5433d55e26e06ededeb0fb3f714548ea98192b012f6de41ebb795930b624f236` |
| `run_native_ssh.ps1` | `e70a22a81acf0b9da1ee76dd2dbd5e6fc93f029cb26fe9630696f345e7eca7a7` |
| `check_roundtrip.py` | `4b232943e28287dbf71cfa842ae884691f2484c246a564abec4ac8fe9ee7ae2d` |
| `validate_native_cli.py` | `550730bef8cce37fadd48583ea6f560aaee6e91abc7c2d89c705877b985b42be` |
| `report_oracle.py` | `623dd8c5ca6cdd83a927b55aa43b0aa85a112b52b275c96e6e722ba31a70467e` |
| `self_check.py` | `670ebe94e8826d64f9264fc5a8ae412f504e7677df606b66b2c92d0829846899` |
| `verify_sources.py` | `196cbb959d8f6943eb02ad8939ad7a2a18a9aa3909330a557ffb3684176472c6` |
| `ordinary-input.json` | `b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3` |
| `shortage-input.json` | `fc65462d65c0fea1017f81e41dc283a9a1f666e7b1f42aeb262fc6f5b8384bff` |

## Protected native boundary

Only the root execution controller may invoke these commands, using the exact frozen runner. First, a fresh independent exact-file review must approve the manifest and runner. Then the controller may run the pure `-PreflightOnly` file invocation through SSH with stdin closed:

```powershell
ssh -n -o BatchMode=yes user@127.0.0.1 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.2\run_native_ssh.ps1 -PreflightOnly'
```

The expected result is a new `review/preflight-ssh0-*.json` with the exact manifest SHA, absent run directories, SSH session 0 and `sshd.exe` ancestry, free host mutex, and the protected responsive GUI PID 13340/session 1/start 1790590196826. This mode starts no SIMLOX child. A separate independent `review/independent-prelaunch-go.json` must bind the **actual** preflight file SHA, manifest, contract, inputs, runner, validator, and both run IDs before the controller may invoke the one guarded serial pair:

```powershell
ssh -n -o BatchMode=yes user@127.0.0.1 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.2\run_native_ssh.ps1'
```

The reserved IDs are `c09-var02-v102-ordinary-ssh-20261007-01` and `c09-var02-v102-shortage-ssh-20261007-01`, under this package's ignored `runs/` directory. The runner uses `Global\SimloxIssue18NativeQueue`, checks the exact GUI identity before and after each native child, requires actual native child session 0, waits for each child to exit, and does not terminate or retry it. Each completed arm should contain `invocation.json`, `steps.json`, `closure.json`, `input.json`, import/export/calc/report logs, `model.sxi`, `model.sxo`, `roundtrip-raw.json`, `model.log`, `report-raw.json`, `roundtrip-validation.json`, and `author-validation.json`. A failed arm retains its raw files and `failure-seal.json`; no second run uses that ID.

## Retrieve and replay the raw evidence

The accepted source and raw locations are resolved relative to this package from `contract.json`; `verify_sources.py` checks their original SHA-256 and byte sizes. The direct C09.var04 parent has three run directories under `../C09-var04-remote-maintenance-resource-v1.0.0/runs/`: `c09-var04-local-20261002-01`, `c09-var04-remote-20261002-01`, and `c09-var04-remote-disabled-20261002-01`. Other sealed references are the D02.var05, D03, D12.var04, A17, and D01 run directories named in the contract. The C03 accepted run is at the contract's explicit external absolute path under `C:\Users\user\dev\sim_engine_compiler-b02-v102`. If a referenced directory is absent, restore the original sealed bytes at the declared path and recheck SHA/size; do not replace them with a new calculation.

After both new closures exist, replay each arm **read-only** from its sealed run directory:

```powershell
$ordinary = Join-Path (Get-Location) 'runs\c09-var02-v102-ordinary-ssh-20261007-01'
$shortage = Join-Path (Get-Location) 'runs\c09-var02-v102-shortage-ssh-20261007-01'
& $python -X utf8 .\check_roundtrip.py $ordinary ordinary
& $python -X utf8 .\validate_native_cli.py $ordinary ordinary
& $python -X utf8 .\check_roundtrip.py $shortage shortage
& $python -X utf8 .\validate_native_cli.py $shortage shortage
Get-FileHash (Join-Path $ordinary 'closure.json'), (Join-Path $shortage 'closure.json') -Algorithm SHA256
```

The roundtrip gate requires all 32 table definitions and 25 row-containing authored tables, including populated cells and metadata; native all-null placeholders are classified separately. The validator rechecks the source and closure hashes, six guarded steps, exact converter contexts (errors 0, warnings #108 and #126 twice, notice #292), physical HOME-PM9 request/wait/work and typed P-MECH loan/return cycles, terminal resource and system state, and **all 1,754 cells per arm** across ProblemDescription, ResultSummary, SystemResults, StockTotalResults, ResourceResults, and ResourceResultsTotal. It derives expected values from the frozen input and complete event log. Source/event-derived whole bins are exact even beside a printed boundary: the accepted h8 control must reject `[7.5,8)` NSYMO `0→0.00001` and `[8,8.5)` NSYMO `2→2.00001`. Only genuinely fractional event-derived exposures have declared field-specific printed-time bounds; an interior FTMO count/fleet ratio has serialization-only precision. The independent reviewer must separately replay the sealed raw and compare the paired result before any bounded acceptance or publication. The eventual evidence index must pin every original raw byte and both closures; no SHA from a newly generated run substitutes for a pinned accepted parent.

## Diagnose a failed gate

- **Pin or path failure:** compare `verify_sources.py` output with `contract.json` and `prelaunch-manifest.json`. Check local bytes and published Git bytes separately. Restore only the exact original sealed file if it is missing; do not normalize its line endings or rerun an accepted parent.
- **Preflight or guard failure:** inspect the emitted SSH preflight record or runner error for session 0, `sshd.exe`, mutex, exact GUI start/responding identity, absent run IDs, and source hashes. No native child should have started in `-PreflightOnly` mode. A new approval must bind a clean new preflight; do not bypass a failed guard.
- **Converter or roundtrip failure:** inspect `run.log`, import/export logs, `roundtrip-raw.json`, and `roundtrip-validation.json`. The contextual diagnostic set and all authored cells are frozen gates; do not reinterpret an unanticipated warning as acceptance.
- **Physical or report failure:** inspect `model.log`, `author-validation.json`, `report-raw.json`, `steps.json`, `closure.json`, and `failure-seal.json` if present. A PM task object alone does not establish performing work. Confirm the actual HOME shortage overlaps the same observed P-MECH loan cycle, and associate transport start/arrival by task ID and typed station receipt. Compare source-derived system/resource/stock ledgers and every report cell; a different random path is evaluated from its own events, not forced to the old parent's times. Any unexplained state, nonterminal task/loan, or report mismatch is a sealed NO_GO for this frozen contract.

The v1.0.0 [excluded contract](../C09-var02-lender-shortage-v1.0.0/contract.json) and [formal NO_GO](../C09-var02-lender-shortage-v1.0.0/review/independent-contract-no-go-2026-10-07.md) remain unchanged; no v1.0.0 child native run occurred. Its [transcript patch record](../C09-var02-lender-shortage-v1.0.0/review/excluded-transcript-patch-mistaken-draft-2026-10-07.md), SHA-256 `77320b0d0a4713a9ba53ac66d3df624393b77e91ffbbabe8e660594e17e05e4f`, preserves available patch text as data, without claiming recovery of unavailable original-file bytes. The v1.0.1 [frozen manifest](../C09-var02-lender-shortage-v1.0.1/prelaunch-manifest.json) and [NO_GO_PURE_PREFLIGHT](../C09-var02-lender-shortage-v1.0.1/review/independent-pure-preflight-no-go-2026-10-07.md) remain intact; v1.0.1 had no actual SSH preflight or native child. Its [boundary calibration](../C09-var02-lender-shortage-v1.0.1/review/independent-boundary-calibration-2026-10-07.md) documents the h8 exact-value defect. The required SHA/size pins for these historical records are in the v1.0.2 contract. A changed source, hypothesis, guard, or report interpretation requires a new version, new unique run IDs, and fresh independent review before another native attempt.

Advisory local context, **not required parents**: the root controller's ignored [v1.0.1 read-only proof](../../../tmp/c09-var02-v101-excluded-readonly-20261007.json) has SHA-256 `ba9d75cbbb0089e92a0a9669f9772a98c629be12ce1b49448f942bbe0d57ee9c`. The independent [D05 waiting-context receipt](../C09-var02-lender-shortage-v1.0.1/review/independent-d05-context-pin-2026-10-07.md) has SHA-256 `306d3c7b881dec4bea6eab7fb1795b8b8471758616f693174f9a1edb4a66f9c8`; the [FTMO context receipt](../C09-var02-lender-shortage-v1.0.1/review/independent-ftmo-context-pin-2026-10-07.md) has SHA-256 `35364c55f3ec103dfe05c99edaec19dfdc9e439e8ef0312daf819fe2118abc51`. They inform interpretation but do not substitute for the accepted C09 parent raw or the frozen v1.0.2 contract.

This case is limited to one seed and one combined three-system 12-hour CLI topology. It cannot establish a persistent mechanic person ID, a general lender-priority or TTRSS law, GUI visual behavior, cross-engine equivalence, or performance. The protected GUI session is an execution guard, not a visual result.
