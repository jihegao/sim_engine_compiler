# I03.var05: one zero-delay IN transfer

This prospective CLI case changes exactly `ProblemDescription.PDESC` and the
existing P-CREW IN row's `TFDT` from 0.5 to 0. The accepted I03.var01
`out_in` run is a read-only comparator. Its OUT row at h7.75, two aircraft,
opening P-CREW quantity 2, two missions and all other 225 authored cells stay
fixed. This package proposes one new run,
`i03-var05-in-zero-delay-v100-ssh-20261008-01`.

[`contract.json`](contract.json) is the frozen v4 prospective design, including
all full-report and event gates. Its `CONTRACT_DESIGN_ONLY` phase records the
state when it was independently approved. [`execution-contract.json`](execution-contract.json)
binds that exact design to this package, input, run name, methods and future
approval flow. Neither file authorizes a native launch by itself.

The falsifiable child expectation is that task 2 starts, arrives and yields a
separate local P-CREW receipt at h10. Task arrival first creates a pending
receipt; only the matching P-CREW receipt raises the derived local roster from
1 to 2. At h8 the OUT backorder reserves the first freed crew; its positive
departure removes one local crew exactly once. The validator separately checks
local, booked, reserved OUT, departed OUT, pending IN receipt, received IN,
nominal quantity, missions and terminal state. These are task-quantity
inferences within this fixed trace, not observed individual crew identities
or a persistent outside pool.

The report oracle derives all 5,210 cells from the frozen source, typed events
and declared native presentation conventions. Its secondary comparison to the
accepted parent predicts seven changed cells: PDESC; NR, NRA and NRN for
h10–10.5; and their three binary32 total means. The five System zero fields,
empty-stock PNB and undefined nulls are bounded presentation expectations,
not general statistical formulas.

The authored input has 32 tables, 25 stored rows and 227 stored cells. Native
export is expected to add exactly one all-null placeholder row in each of 11
otherwise empty tables, yielding 32 tables, 36 rows and 368 cells with full
metadata preserved. The six serial stages are import, export,
check_import_export, calc, jsonreport and check_behavior. After calc and before
jsonreport the runner seals `model-run.log` and requires the exact converter
paths, warnings #108/#126, and Errors 0 / Warnings 2 / Notes 0.

Only the root coordinator may run the exact reviewed SSH5 preflight and native
sequence. This package carries a fixed neutral transport, binary-preserving
capture helper, source inventory, full validators and self-checks for later
independent source review. No new native result is claimed here.
