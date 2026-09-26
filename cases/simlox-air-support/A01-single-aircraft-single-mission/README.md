# A01 — one aircraft, one mission

Version `1.0.0`; no parent. This is a generic teaching aircraft at one base. [Contract](contract.json) was written before [native input](native-input.json). One scheduled wave at 8 h, ordered at 7 h by the explicit 1 h notice lead, occupies one aircraft for 2 h, then completes at 10 h. Horizon 36 h. Expected mission-operation interval integral is 2 h = 120 min; this does not separately measure airborne phases. Planned waves, launches, sorties and completions are each 1; cancellation and unfinished count are 0. All rates and capacity constraints unrelated to this slice are absent or explicitly inert. The native output must confirm these expectations; printed hours are not treated as infinite precision.

Files: [parameters](parameters.json), [SIMLOX field and GUI mapping](mapping.csv), [manifest](manifest.json), [result summary](results-summary.json), [acceptance](acceptance.json), [evidence index](evidence-index.json). Null native columns are left null and their behavior is recorded by exact import/export roundtrip; no undocumented default is asserted. `MissionType.TFOUT/TFRET=0.25` are explicit phase fractions; native `SystemResults.FTMO` must integrate to 2 h. The final input omits `MissionPreparation` entirely. An initial zero-duration row caused native `NPSTA=1`; removing it made `NPSTA=0` while the log still emitted same-time preparation lifecycle markers. Both raw runs are retained.

Fresh reproduction on 4700-3: from the repo directory, generate to a **new** path with `& 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe' cases/simlox-air-support/tools/generate_native.py --case A01 --output data/local/simlox-case-library/generated/a01-replay-input.json`; compare SHA to the checked input; then invoke `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File cases/simlox-air-support/tools/run_native_bound.ps1 -CaseId A01 -RunId a01-replay-UNIQUE -InputSha256 <checked-input-sha>` through the coordinator SSH PowerShell path. The runner always reads the checked input and writes an immutable run directory; generated copies are for byte-level verification.

GUI calibration/review is pending. The 20-minute delay deadline is observable only if an aircraft is unavailable or preparation blocks it. A01 intentionally has neither, so no cutoff-priority claim follows from a normal launch.

Use these exact commands in the coordinator SSH PowerShell context on 4700-3, with a fresh run ID when repeating. The generated file is a separate byte-reproduction check; the runner uses the checked case input.

```powershell
$repo = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo'
Set-Location -LiteralPath $repo
$py = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path "$repo\data\local\simlox-case-library\generated" | Out-Null
$suffix = [Guid]::NewGuid().ToString('N').Substring(0,12)
$generated = "$repo\data\local\simlox-case-library\generated\a01-$suffix.json"
& $py "$repo\cases\simlox-air-support\tools\generate_native.py" --case A01 --output $generated
if ((Get-FileHash -LiteralPath $generated -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7') { throw 'generated input changed' }
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$repo\cases\simlox-air-support\tools\run_native_bound.ps1" -CaseId A01 -RunId "a01-repro-$suffix" -InputSha256 8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7
```

The generated SHA must equal the checked input SHA above. `run_native_bound.ps1` refuses an existing output directory or active SIMLOX process and preserves all output under ignored `data/local`.
