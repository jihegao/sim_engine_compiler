# I03.var06: fixed OUT duration classification

This prospective CLI pair changes only `ResourceTransfer.TFDT` from `0` to `4` and the authored problem description in the accepted I03.var02 idle OUT input. The accepted parent is reused read-only. The child has **not** been run or accepted at this stage.

The installed manual states that TFDT is ignored for an OUT transfer. The frozen contract requires the exported child source to retain `TFDT=4`, a single typed h6 OUT transfer of one `P-CREW`, no delayed h10 arrival, complete physical and nominal resource conservation, and all 5,210 child report cells checked from the source and typed event timeline. Of the corresponding parent and child cells, 5,209 are predicted equal; `ProblemDescription.PDESC` changes by authorship. Five resource means are compared to their exact binary32 values. Declared native presentation constants are checked as such.

The source input, oracle, runner and replay are subject to independent static review, an actual SSH5 preflight, separate prelaunch approval and sealed postrun review. A synthetic child fixture exercises the checker but supplies no native evidence. There is no claim about IN, BETWEEN, a general TFDT law, GUI behavior, performance or another engine.

See [REPRODUCTION.md](REPRODUCTION.md) for exact static and future guarded execution steps. The frozen [contract.json](contract.json) and [development-note.md](development-note.md) define the scope and historical provenance.
