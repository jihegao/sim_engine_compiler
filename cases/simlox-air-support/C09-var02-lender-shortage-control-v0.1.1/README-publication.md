# C09.var02 — observed lender wait control

This package classifies one sealed 12-hour SIMLOX CLI run. The HOME aircraft's scheduled PM requests a mechanic at BASE-02 while its only P-MECH unit is loaned to BASE-01. The request fails at h9; HOME waits until the unit returns at h9.96988, then performs PM through h10.2199. The source sets both TTRSS and TTRS to 0.5 hour, so this run cannot distinguish which return-duration branch was used.

The original v1.0.2 prospective pair remains **NO_GO**. Its ordinary-arm behavior checker failed and the shortage arm was never started. This retrospective replay adds no native run and does not approve the old pair. The author and independent replays separately reconcile all 1,754 cells across the six selected report tables, physical task/transport/resource events, and original source/raw seals.

The original [README.md](README.md) is the immutable contract-stage snapshot. The [contract](contract.json) defines this bounded claim; the [reproduction guide](REPRODUCTION.md) gives read-only commands, raw paths, expected results and failure diagnosis. [Scope signoff](cli-scope-signoff-2026-10-07.md) records the limit, and [evidence-index.json](evidence-index.json) lists exact source and raw byte pins after the publication gate. The root publication index determines current publication status.

No persistent mechanic-person identity, general lender priority, conditional TTRSS effect, GUI behavior, cross-engine behavior or performance result follows from this control.
