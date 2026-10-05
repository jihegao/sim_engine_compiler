# D01.var01 matched zero-FRT control

This candidate derives from the accepted D01 installed-LRU source. It changes
only `System.FRT` and `Item.FRT` from `300000` to `0`, plus the description.
The accepted D01 source and its run are never regenerated. The expected native
converter diagnostics are zero errors, warning #108 for logging, and warning
#2053 for the deliberately zero Item FRT. Any other diagnostic excludes this
positive candidate and the failed raw evidence must be retained.

The predeclared CLI question is whether all three scheduled two-hour missions
complete without failure, replacement demand, or repair while the single
physical local spare remains on hand. The native log and all 72 half-hour
system and stock report rows require independent replay before acceptance.
`StockTotalResults.PNB` is not a physical on-hand quantity. GUI observation,
cross-engine equivalence, and general zero-failure behavior are unverified.

`build.py` reconstructs the frozen `native-input.json`; `check_parent_diff.py`
checks all 257 business cells; `run_native_ssh.ps1` is the one-use serial native
candidate runner. The original `validate_native_cli.py` is preserved with its
independent prelaunch NO_GO; the runner pins `validate_native_cli_v011.py`.
That versioned validator's first read-only replay failed one source filename
lookup. `validate_native_cli_v012.py` corrects only that lookup and passes on
the same sealed run. The ignored `runs/` directory holds raw local evidence
and is never overwritten.
