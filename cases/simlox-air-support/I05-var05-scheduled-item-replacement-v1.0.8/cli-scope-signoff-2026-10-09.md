# I05.var05 bounded CLI scope signoff — 2026-10-09

## Decision

Accept `I05.var05` version `1.0.8` for the bounded CLI scope backed by the sealed v1.0.7 native run `i05-var05-item-replacement-v107-ssh-20261009-01`. Version 1.0.8 is a corrected-checker replay candidate; it did not launch a native process. The original v1.0.7 runner result remains `NO_GO` and is not rewritten.

## Accepted parent and change

The direct accepted parent is published `H02.var04` v1.0.0, run `h02-var04-item-fallback-v100-ssh-20261002-01`. The child retains its ordinary `ItemReplacement` row and adds one `ChangesItemReplacement` row at hour 5 for `TEACH-AIR-01 / TEACH-LRU-01 / BASE-01`, changing `SURPT` from 1.0 to 1.5 hours. The accepted parent was not rerun. The exact local and publication-index parent pins are retained in the v1.0.7 source freeze and manifest.

## Evidence and independent review

The v1.0.7 run imported, exported, roundtripped, calculated, and produced a report with exit zero; conversion reported zero errors, two warnings, and zero notes. The original behavior validator then exited 1. The complete raw set and transport stderr are byte-sealed in the v1.0.7 failure seal (`90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0`).

A09 independently verified the sealed files and replayed the physical events and selected report scope. A17 reviewed the contract and the two checker errors, then independently replayed v1.0.8 on a private writable copy of the sealed log/report. Its separate receipt-bound decision is `GO_BOUNDED_POSTRUN` (`2a2b3d2da9095cff81d2a7d036a587baf292951c6aeb2f9c2c93cc1aee013ffb`). The source freeze is `078ed313c0dd522d0753852b6f70613c8b15cca2708487c56cc44b8a41224fff`; the corrected validator is `632e4e9c9d38d1e81382c82a89f12dab165a7a92930b310e2f415667ac1028f9`.

## Assertions accepted

- No system SURP task starts at the hour-5 change time.
- Three later system SURP tasks last 1.49995, 1.5, and 1.5 hours, within the frozen tolerance.
- Damaged item identities reconcile through demand, spare issue, removal, direct repair, arrival, and stock return; subsequent spare draws follow prior repaired stock returns.
- The report matches the accepted four-table roster and ordered schemas. All 4,044 typed cells are retained; only the declared event bins, partitions, exposure, failure counts, and terminal summary fields are asserted.

## Limits

This is a bounded result for one source, seed, station, and mother/child item relationship. The replay does not accept the failed v1.0.7 runner invocation itself; it establishes that the corrected v1.0.8 checker passes the existing sealed run. Other report metrics, GUI behavior, other change fields or timing boundaries, general stochastic behavior, cross-engine equivalence, and all of I05.var05 remain unverified. This signoff does not complete Issue 18.
