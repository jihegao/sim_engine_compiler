# D15.var01 v1.0.0 excluded PMRF diagnostic

This fixed-seed pair is retained as a reproducible diagnostic, not a published Issue #18 case. It derived a system CAL24 scheduled one-LRU exchange from accepted D14 item stock geometry, with PMReplacement.PMRF 1.0 versus 0.5 and four observed PM opportunities through h120. Both arms imported, exported, calculated and reported under guarded session-0 SSH with converter Errors 0, Warning #108, Notes 0. The event logs were byte-identical: both arms requested and fitted a physical replacement at h24, h48.5, h73 and h97.5. The PMRF=0.5 arm had no observed no-exchange opportunity, so the frozen mixed-outcome acceptance hypothesis failed. The planned selected `ItemResults` export was not executed for this excluded version.

The native run is `runs/d15-var01-pmrf-v100-ssh-20261004-01` (local, ignored), closure SHA-256 `7f2582fd238f583b9351c826389ec60071b39a07f0f09a8b536ba54631a3a85c`. Independent replay passed 1,443/1,443 evidence checks but returned `NO_GO_FULL_CONTRACT` in `review/independent-verdict.json`. No publication-index entry points to this package.

The separately frozen `D15-var01-pmrf-seed-panel-v1.0.1` keeps the same geometry and PMRF pair and prespecifies seeds 2–6 to test both outcomes across a panel. Its result is evaluated under a new contract and native closure.
