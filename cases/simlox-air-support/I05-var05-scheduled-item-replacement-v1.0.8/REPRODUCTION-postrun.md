# I05.var05 v1.0.8 postrun reproduction

This is a read-only replay of the already completed v1.0.7 SIMLOX run. Do not invoke SIMLOX, SSH, or `run_native_ssh.ps1`; do not rerun H02.var04. The v1.0.7 failure seal and 14-file raw directory remain unchanged and are checked by `evidence-reference.json`.

The complete v1.0.7 `runs/` tree, including `model.sxi`, `model.sxo`, report, logs, and remaining raw outputs, is host-bound and excluded from the staged publication set. A published checkout alone cannot perform the full replay. The operator must have the exact host-bound raw files available at the pinned source path and verify every one against the v1.0.7 failure seal and evidence references. This package currently includes no curated raw log copies; the staging allowlist names only files that are present and reviewed.

Use a new temporary replay directory because `validate_native_cli.py` writes a derived `physical-stock-ledger.json` beside its log/report inputs. The recorded A17 replay did this only in a private copy and preserved before/after source custody.

```powershell
$case = 'C:\Users\user\Documents\Codex\2026-09-29\i05-var05-worktree\cases\simlox-air-support\I05-var05-scheduled-item-replacement-v1.0.8'
$sourceRaw = 'C:\Users\user\Documents\Codex\2026-09-29\i05-var05-worktree\cases\simlox-air-support\I05-var05-scheduled-item-replacement-v1.0.7\runs\i05-var05-item-replacement-v107-ssh-20261009-01\raw'
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$replay = Join-Path $env:TEMP ('i05-v108-replay-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $replay | Out-Null
Copy-Item (Join-Path $sourceRaw 'model.log') $replay
Copy-Item (Join-Path $sourceRaw 'report-raw.json') $replay
Push-Location $case
& $py -B -m unittest test_surp_event_parser
Pop-Location
& $py -B (Join-Path $case 'validate_native_cli.py') $replay
```

The two parser regressions and corrected validator passed in A17's independent private replay. The validator output lists the physical ledger hash and the selected report scope. Reproduce the source and external evidence pins from the frozen source map and confirm the v1.0.7 raw directory still contains exactly the 14 files recorded in its failure seal. No unasserted report metric should be promoted to an accepted claim.
