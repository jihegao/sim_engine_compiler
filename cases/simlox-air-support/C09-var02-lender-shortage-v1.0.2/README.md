# C09.var02 lender shortage — frozen prelaunch snapshot

This file records the prelaunch state of the v1.0.2 matched pair. The central `publication-index-v1.json` is the authority for its later publication status. The v1.0.0 contract NO_GO and v1.0.1 pure-preflight NO_GO remain excluded diagnostics with their original bytes pinned. v1.0.2 retains the v1.0.1 model and corrects its report comparison: source/event-derived whole-bin values stay exact even beside a printed boundary; only genuinely fractional exposures use declared field-specific time bounds, and an interior count/fleet FTMO ratio uses serialization precision.

The accepted C09.var04 remote input supplies the borrower and one P-MECH at BASE-02. Both new arms add the same fault-free HOME-AIR and its 9-hour calendar PM requiring that mechanic, enable PM, and shorten the horizon and collections to 12 hours. The ordinary arm sets TTRSS to 0.5 hours, equal to ordinary TTRS; the shortage arm sets TTRSS to 0.125 hours. Both must independently show a physical lender shortage before a return duration can support the conditional-return claim. The other paired difference is the problem description.

The 32-table inputs and complete parent/pair row diffs are produced by `build.py`. `verify_sources.py` checks accepted disk and published Git bytes, 117 accepted raw seals, nine invocation/closure pairs, installed program and manual pins, and the excluded v1.0.0 and v1.0.1 evidence. `check_roundtrip.py` checks all 25 row-containing authored tables and metadata after a native import/export. `validate_native_cli.py` derives physical event and report expectations from the frozen sources and log; it does not use the child report as its own oracle. `self_check.py` rehearses all 5,210 cells against the accepted C09 control and rejects synthetic event, diagnostic, metadata, and report changes, including h8 `NSYMO` zero/count changes by 0.00001 and excess interior FTMO drift. Source integrity is checked by `build.py` and `verify_sources.py`.

Reproduce the static checks with the bundled Python runtime:

```powershell
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -X utf8 .\build.py
& $python -X utf8 .\verify_sources.py
& $python -X utf8 .\self_check.py
```

The guarded native runner is reserved for the root controller after a fresh exact-file independent prelaunch approval and an actual SSH0 `-PreflightOnly` pass. It waits for every child to exit and never terminates or retries native work. Any failed converter, shortage, return, full 1,754-cell-per-arm report, or terminal gate is a sealed NO_GO diagnostic. A changed hypothesis requires a newly versioned contract and review.
