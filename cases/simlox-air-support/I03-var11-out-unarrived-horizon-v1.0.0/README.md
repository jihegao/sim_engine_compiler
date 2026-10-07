# I03.var11: OUT task unarrived at horizon

This package tests one prospective CLI source change from the accepted I03.var02 idle crew OUT case: `ResourceTransfer.TFDT` changes from 0 to 40 and `ProblemDescription.PDESC` identifies the case. The accepted parent run is reused byte for byte. No var11 native run is accepted by this README.

The hypothesis is that the quantity-one OUT task starts at h6 with a printed duration of 40 and has no linked arrival or cancellation through the h36 simulation horizon. The terminal value is a **derived started-but-unarrived task quantity**, not an observed person or outside-pool location. h46 is arithmetic only. The installed manual's OUT-delay wording conflicts with the fixed TFDT4 failed witness; the exact installed bytes and this row are the scope of the test.

The frozen [contract](contract.json) fixes source, typed event, report, numeric and provenance gates. `build.py` verifies the child source read-only by default; `--write` was used once during construction. `verify_sources.py`, `test_sealed_catalog.py` and `self_check.py` are read-only. The synthetic child fixture only checks whether these gates can reject changes; it is not native evidence.

An actual SSH5 preflight requires an independent pure-source review. One native child requires a fresh, exact-file independent prelaunch approval after that preflight. Native execution and publication are controlled by the root task. A native divergence remains NO_GO and its original files are preserved.
