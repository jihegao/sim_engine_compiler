# I03.var02 idle crew OUT — contract snapshot

This is a prelaunch contract for one new CLI child. It compares an idle `P-CREW` OUT request at hour 6 with the sealed I03.var01 busy OUT request at hour 7.75. The child changes only `ResourceTransfer.TFTIME` and `ProblemDescription.PDESC`; the accepted parent is not rerun.

The planned child has two initially allocated crew and two two-aircraft mission waves. At hour 6 both crew should be idle, so one unit should leave immediately without a transfer backorder. One remaining crew should prepare the two aircraft serially for each wave. The contract makes the predicted launches at hours 8.5 and 20.5 falsifiable against native events, resource quantities, and every cell of the six-table report. The scheduled mission deadlines are hours 9 and 21. The busy parent instead backorders its OUT at 7.75 until hour 8, so its first launch stays at hour 8.

The [contract](contract.json) pins the parent and prerequisites, defines full source and report gates, and records the current case limits. It remains `contract_only`; no child input, runner, preflight approval, or native run exists in this package. Independent contract review must precede construction. Published state will be governed by the central catalog after its separate publication gates.

This bounded test covers one seed, base, personnel type, OUT quantity, and pair of missions. Zero available crew, BETWEEN, equipment, batching, priority, shifts, maximum utilization, rest status, GUI behavior, performance, and cross-engine equivalence are outside its scope.
