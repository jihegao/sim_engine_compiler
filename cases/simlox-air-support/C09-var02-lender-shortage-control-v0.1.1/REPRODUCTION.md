# Read-only reproduction — C09.var02 lender-wait control

## Inputs and raw location

Use the source and SHA/size records in [contract.json](contract.json) and [evidence-index.json](evidence-index.json). The only replayed native directory is the ignored local `../C09-var02-lender-shortage-v1.0.2/runs/c09-var02-v102-ordinary-ssh-20261007-01`. Its closure, invocation, failure seal and thirteen raw files are pinned separately. The v1.0.2 shortage-arm directory must be absent. If the ignored run is unavailable in a fresh checkout, retrieve the preserved original byte-for-byte run evidence from its evidence custodian; do not recalculate, substitute a new run, or normalize its JSON/log line endings. Rehash every restored file against the contract before interpreting behavior.

The [raw custody map](raw-custody-map.json) gives the exact SHA-256 and byte size of **all nine accepted dependency closures and invocations, all 117 dependency raw files, and the sole failed ordinary run’s closure, invocation, failure seal and thirteen raw files**. The source verifier requires the full set, not just the ordinary run. The C03 staffing-2 original is in the separately preserved `C:/Users/user/dev/sim_engine_compiler-b02-v102` checkout; the other accepted run paths are repository-relative. Retrieve each exact original before running the verifier. The custody map lists every path and file identity; it is a retrieval reference, not permission to recalculate.

| Accepted original run | Closure SHA-256 | Raw files |
| --- | --- | ---: |
| `../../../../../../../../dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C03-shared-crew-formation-v1.0.2/runs/c03-v102-staff2-ssh-20260929-04` | `7f8f26da9d48758838635968a5ec878ea079b6ca6cf00feb8b755ea4573ff92a` | 11 |
| `../A17-multi-unit-group-v1.0.0/runs/a17-v100-ssh-20260929-01` | `f1885aa1c21bf2260d1d7671e762d18451d91a0fc0398cf45309574d16c2f76b` | 12 |
| `../C09-var04-remote-maintenance-resource-v1.0.0/runs/c09-var04-local-20261002-01` | `028032445d1da0d99082e7f114977d49273d5e4d1d7d9b737cdea4bc6147225b` | 12 |
| `../C09-var04-remote-maintenance-resource-v1.0.0/runs/c09-var04-remote-20261002-01` | `649cdaaae5fd872da32fcc850d3f491bf0b69c17a9856f84ade6a7f4a10fbd1a` | 12 |
| `../C09-var04-remote-maintenance-resource-v1.0.0/runs/c09-var04-remote-disabled-20261002-01` | `040a794d12ebb68e539578fd8486b047c0996712cb8748bf0b0795db83f2d72d` | 12 |
| `../D01-installed-lru-direct-repair-v1.0.0/runs/d01-lru-v100-ssh-20260929-01` | `3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0` | 12 |
| `../D02-var05-zero-operating-exposure-v1.0.2/runs/d02-var05-zero-op-v102-ssh-20260930-01` | `2cfbeb852e4d78ae8c3e6df9b024bd25d6fbc582c943f5fda6dff008f5a503ac` | 12 |
| `../D03-calendar-pm-v1.0.0/runs/d03-calendar-v100-ssh-20261001-02` | `9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8` | 12 |
| `../D12-var04-remote-critical-v1.0.1/runs/d12-var04-remote-critical-v101-ssh-20261004-01` | `2cdc10a5ac59bf3b5691840f712a91013de2fc6687151622a7f1e758da6a4db1` | 22 |

The sole failed ordinary run is `../C09-var02-lender-shortage-v1.0.2/runs/c09-var02-v102-ordinary-ssh-20261007-01`. Closure `30a99a36775224096dae27e938495dae5e12bb441cd493c2312baf5bef58d5df`, invocation `ed2e0c12f69caac6f37597cd454a71190e9260a6726d450120a62708a694d756`, failure seal `43a64a32e56abdcf312482c16d56b391f6bb5eb0d939efa272a330e4ff86c73e`; its thirteen individual raw SHA/size records are in the same custody map. The v1.0.2 shortage run is absent.

The older v1.0.0 contract and NO_GO, v1.0.1 pure-preflight NO_GO, and v1.0.2 prospective failure are historical exclusions. The published accepted C09, C03, A17, D01, D02, D03 and D12 source identities include separate local-disk and Git-byte pins where needed. The installed SIMLOX executable, manual and dictionary are referenced by SHA and path; their binaries are not copied into this package.

## Commands

From the repository root in PowerShell, with the bundled Python runtime:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case = 'cases/simlox-air-support/C09-var02-lender-shortage-control-v0.1.1'
& $py -X utf8 "$case/verify_sources.py"
& $py -X utf8 "$case/validate_native_cli.py"
& $py -X utf8 "$case/self_check.py"
& $py -X utf8 "$case/review/independent_replay.py"
```

These commands only read original source and raw evidence and print deterministic JSON. Do not redirect output into a sealed run directory. Expected author result: `GO_BOUNDED_RETROSPECTIVE_CONTROL`, 1,754 report cells, zero failures, no new native run; the author self-check rejects 23 in-memory mutations and accepts two documented within-bound representations. The independent replay should separately return its bounded GO with all 1,754 cells and 26 semantic tamper rejections. Exact script, verdict, memo and raw hashes belong in the evidence index. The old v1.0.2 author verdict remains a failed prospective result.

## What is checked

The verifier checks source and accepted-run SHA/size pins, separate Git bytes, the v1.0.2 256-record prelaunch manifest, thirteen ordinary-arm raw seals, fifteen failure-seal file pins, original approval/preflight identity, and absent shortage-arm run. The validator checks the 32-table input and 25 row-containing authored tables, converter contexts, six recorded steps, typed P-MECH loan/return and HOME wait/PM task identities, resource/stock conservation, terminal state and all 1,754 report cells. The PM parser recognizes the native bare `subtask ... within system PM task` lines.

For event-derived numeric cells, the frozen contract uses half the last printed decimal unit per event time, propagates signed state-edge uncertainty through each stated denominator, then adds at most 5×10⁻⁷ report serialization allowance. Exact IDs, nulls, discrete counters and genuine whole bins have zero slack. Only HOME [9,9.5) System.NSYWR and Resource.NRW have the named ≤3×10⁻⁶ retrospective representation exception; interior FTMO 2/3 has serialization-only ≤5×10⁻⁷. The self-check mutates those limits and physical events in memory, after source seals are checked.

## Failure diagnosis and limits

An absent or mismatched raw file is a provenance failure: restore the original sealed bytes and rerun the read-only verifier. A parser error on PM work should be checked against bare native subtask start/completion tokens, not repaired by editing raw logs. A resource or state-ledger mismatch requires tracing task IDs, stations, failed availability, bookings, transfers and releases in the original model log. A fractional-cell failure requires checking the source-derived expression, printed edge precision, denominator, class ceiling and native report serialization; never fit a tolerance to the reported candidate cell. Preserve any NO_GO output as a new diagnostic record.

The run shows physical lender wait and one 0.5-hour return, with TTRSS=TTRS=0.5. It cannot establish a distinct conditional return duration. Any new input or native test requires a separate versioned contract, fresh source/runner pins, independent review and unique run ID; these commands do not grant that approval.
