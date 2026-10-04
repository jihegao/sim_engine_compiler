# D13.var05: repeated, nested PM activation profile

This paired SIMLOX 2017 case derives from the accepted [D13 local PM activation case](../D13-var01-pm-activation-v1.0.0/README.md). The [flat input](flat-input.json) gives ten explicit adjacent six-hour `PMActivationProfile` periods, alternating `ENPM=N/Y` over 60 hours. The [nested input](nested-input.json) defines one 12-hour `PM-HALF` child profile (`N` for six hours, then `Y` for six) and repeats it five times through `PM-ROOT` with `IQTY=5`, `IINT=12`. The [builder](build.py) pins the accepted parent, and the [contract](contract.json) freezes the comparison.

Both arms have one aircraft, one local CAL24 PM, the same three missions and seed. Their native event logs are byte-identical to each other and to the accepted parent: PM physically works at hours 30–31 and 55–56, and all three missions succeed. The non-description report tables also match. See the [bounded sign-off](cli-scope-signoff-2026-10-04.md) for source and report reconciliation and limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks, and a targeted 60-second child watchdog. Its raw run is ignored by Git; the [evidence index](evidence-index.json) publishes sizes and SHA-256 hashes for 22 files. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) verify the sealed run without invoking SIMLOX.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D13-var05-repeated-pm-profile-v1.0.0\validate_native.py
```
