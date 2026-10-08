# I03.var05: zero-delay IN, bounded original trace

This package compares the accepted I03.var01 `out_in` run with one new SIMLOX
run. The authored child input changes only ProblemDescription.PDESC and the h10
IN ResourceTransfer.TFDT from 0.5 to 0. The h7.75 OUT transfer, opening
P-CREW quantity two, horizon and other source cells remain fixed. The
accepted parent was not rerun.

The child's original log prints the IN task start and arrival at h10, followed
by a separate local P-CREW receipt at h10. The task-arrived state does not
itself increment the local roster; the receipt does, once. The eventwise
ledger ends with local quantity two, no outstanding OUT reservation and no
pending IN receipt. The parent receives locally at h10.5. This is evidence
about these source rows and installed SIMLOX bytes, not a claim about an
outside-person pool or other transfer setups.

The frozen author validator checks the entire typed child log (184 timed
events in 250 lines), exact source and export topology, and all 5,210 report
cells. The independent reader directly checked the accepted parent and new
child, 5,210 report cells per arm and 248 supported physical microsteps, and
found seven paired cell differences. It returned GO_BOUNDED with 70,095 checks
against the original sealed child run. The six serial
native/checker stages returned integer exit code zero. The calculated
converter log records Errors 0, Warnings 2, Notes 0 with the declared Control
#108 and System #126 warnings. [The independent postrun memo](review/independent-postrun-go-2026-10-08.md)
states the bounded acceptance gate.

Whole-valued report cells and exact binary32 ResourceResultsTotal means are
checked against source/event expectations. Declared empty-stock and System
presentation zeros/nulls are bounded native conventions, not inferred
statistics. The seven paired differences are the description cell, three
10–10.5 resource cells (NR, NRA, NRN), and three resource total means. NRUM
and NRW totals remain the predeclared values.

The [evidence index](evidence-index.json) pins frozen prelaunch sources,
accepted original context, the one new original run, approvals, original
binary captures and review findings. The historic 494-entry catalog archive
and base Git blob have distinct byte identities; sealed replay always checks
the live catalog's typed first 494 entries, metadata and unique publication
IDs. The prospective [README](README.md) and [contract](contract.json)
remain historical prelaunch artifacts. The current [signoff](cli-scope-signoff-2026-10-08.md)
and [reproduction guide](REPRODUCTION-postrun.md) describe this original run.

Scope excludes general IN/OUT timing laws, transfer identity outside the
local/task ledger, GUI behavior, performance, other engines and all of I03.
Catalog publication becomes effective only after reviewed Git merge.
