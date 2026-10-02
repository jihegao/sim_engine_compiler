# G11.var11: stocked LRU prelife row order

This bounded pair starts from accepted G11.var04 explicit installed-LRU prelife. It sets two initially stocked `TEACH-LRU-01` spares to fixed CALHOURS ages 10 and 70, one each, via top-level `PL-STOCK`. The pair reverses only their `PrelifeData` row order plus description. The installed LRU begins at age20; monitored CAL100 PM, seed1, `IQTY=0` and a 140-hour horizon are common.

Both guarded native CLI runs completed five steps with zero errors/notes and only warning #108. Each exactly roundtripped 23 populated authored tables and sealed 13 local raw files. Prelife Logs retain the input stock age order. At original installed item ID0's h80 PM, both arms issue physical stock ID1 and return ID0 at h81.25. With age10 first, no further PM occurs by h140. With age70 first, ID1 reaches a second system PM at h110.5, item PM h110.75–111.75, and physical ID2 is issued; ID1 returns to stock. The second PM occurs 30 hours after system service completion at h80.5, matching the issued spare's observed age70.

Each arm has 280 contiguous half-hour System/Stock report bins, terminal system ready1, physical stock level2, no backorders or missions, and PM/stock counters matching its one or two PMs. The first issue of ID1 and subsequent difference show row-order effects in this one native setup; they do not establish a general stock-selection priority.

The [contract](contract.json), [source diff](exact-diff.json), [evidence index](evidence-index.json), [author replay](author-validation.json), [independent verdict](independent-validation.json) and [CLI sign-off](cli-scope-signoff-2026-10-03.md) define the evidence. Raw native outputs stay in ignored `runs/`; the index records 26 hashes and sizes. Author replay passed 190/190 checks and a separately written read-only replay passed 27,644/27,644.

This covers one system, two fixed-age same-type spares, one seed and h140. Other age patterns, inventory priorities, longer PM chains, GUI visual behavior and cross-engine parity remain unverified.
