# A02 — the same aircraft on three separated missions

The [2026-09-29 bounded CLI sign-off](cli-scope-signoff-2026-09-29.md) publishes the normal three-wave path as a reusable behavior parent, derived from accepted A01 1.0.0. Frozen candidate status fields retain their original historical state.

Version `1.0.0`; behavior parent `A01@1.0.0`. This case adds only scheduled waves at 20 h and 32 h to A01. The [parent diff](parent-diff.json) must contain exactly two added `OperationProfile` rows and no removals or other table changes. The aircraft, mission template, duration, base, result window and disabled mechanisms are unchanged.

Hand expectations in the [contract](contract.json): notifications 7/19/31 h; starts 8/20/32 h; completions and return to ready 10/22/34 h; three waves, three sorties, 6 h = 360 min cumulative mission-operation interval time, zero cancellations and no unfinished mission at the 36 h horizon. State recovery after each wave, not merely aggregate success, is an assertion. No preparation, fault, PM, CM, stock or resource competition is introduced.

Files: [parameters](parameters.json), [native input](native-input.json), [field and GUI mapping](mapping.csv), [manifest](manifest.json), [result summary](results-summary.json), [acceptance](acceptance.json), [evidence index](evidence-index.json). Fresh reproduction uses `generate_native.py --case A02 --output data/local/simlox-case-library/generated/a02-replay-input.json`, compares the SHA to the checked input, then invokes `run_native_bound.ps1 -CaseId A02 -RunId a02-replay-UNIQUE -InputSha256 <checked-input-sha>` through the coordinator SSH PowerShell path. Both commands must use the absolute new repo workdir.

CLI evidence supports the A01 derivation. Under the [revised case standard](../execution-plan-v2.md#3-证据状态和阶段门), GUI is an optional spot-check and no screenshot archive is required for publication. The dated sign-off above completes the case-level review of frozen CLI behavior, accepted A01 parent, reproducibility and limits. Normal always-ready missions do not exercise before/tie/after cancellation priority.

Use these exact commands in the coordinator SSH PowerShell context on 4700-3, with a fresh run ID when repeating. The generated file is a separate byte-reproduction check; the runner uses the checked case input.

```powershell
$repo = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo'
Set-Location -LiteralPath $repo
$py = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path "$repo\data\local\simlox-case-library\generated" | Out-Null
$suffix = [Guid]::NewGuid().ToString('N').Substring(0,12)
$generated = "$repo\data\local\simlox-case-library\generated\a02-$suffix.json"
& $py "$repo\cases\simlox-air-support\tools\generate_native.py" --case A02 --output $generated
if ((Get-FileHash -LiteralPath $generated -Algorithm SHA256).Hash.ToLowerInvariant() -ne '84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8') { throw 'generated input changed' }
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$repo\cases\simlox-air-support\tools\run_native_bound.ps1" -CaseId A02 -RunId "a02-repro-$suffix" -InputSha256 84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8
```

The generated SHA must equal the checked input SHA above. `run_native_bound.ps1` refuses an existing output directory or active SIMLOX process and preserves all output under ignored `data/local`.
