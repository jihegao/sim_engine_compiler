# I01.var04 — unreferenced item repair under AIR_NONE

This bounded native case tests the SIMLOX manual's rule that an `ItemRepair`
record with no task reference stays active. It uses the accepted I01.var01
stock model and the restricted I01.var05 task-referenced `<NONE>` diagnostic
as its source lineage. The comparison does not accept a general `<NONE>`
reorder or discarded-item disposition rule.

## Frozen comparison

The referenced control is byte-identical to I01.var05 `none-input.json`
(`7dffc0b82a406761f55e1171491dfe9759c22c0123e2397aae4d19d6af7ba286`).
The unreferenced source is
`7873f467594ef1cc2bf65da25b75dbbb3d53769be73cb0196d1eec34a1ce5768`.
Only `ItemRepair.DIRPTID` changes from `I01-LRU-DIRP` to null, plus the
descriptive text. Both retain `Control.APID=AIR_NONE`, one local LRU spare,
the `AIR_NONE/LRU-CM/BASE/<NONE>` maintenance allocation, the same aircraft,
failure seed, mission schedule, and 36-hour horizon. Neither source has an
`ItemReorder` row. `build.py`, `contract.json`, and `exact-diff.json` freeze
this delta; the native runner rechecks their hashes before execution.

## Native result

Two fresh session-0 SSH CLI runs were serialized by
`Global\SimloxIssue18NativeQueue` with GUI PID 13340 preserved. Each
round-tripped all 23 authored nonempty tables, converted with zero errors,
produced a valid nonempty SXO and report, and sealed 12 raw artifacts in its
local Git-ignored `runs/` directory. The same LRU fails at h9.8829, the first
mission aborts, the local spare is issued at h10, and the aircraft is ready
at h10.5 in both runs; the later two missions succeed.

The task-referenced control records arrival of failed LRU ID1 at h10.1667
but no item DIRP or stock return. The converter emits notice #2034 and the
simulation emits warning #241 for incomplete item repair. In the unreferenced
arm, failed LRU ID1 starts a one-hour DIRP at h10.1667, completes at h11.1667,
and returns to local stock at level 1. Its converter has zero notes and the
simulation does not emit warning #241. The changed item path is visible in
the event log and stock ledger. The three business report tables are equal
between arms, including 72 aligned System and Stock bins, so those aggregates
alone cannot establish the item path.

This result supports only the no-task-reference activation rule in this
LRU/WS/BASE-01 configuration. It does not establish resource/stock POINT
pairing, other category or station selections, `StationVariant`, a valid
reorder path for `<NONE>`, complete physical item accounting in the control,
GUI visual behavior, or cross-engine parity.

## Reproduction

Run `build.py` and `describe_diff.py` to verify the frozen source delta.
On the licensed Windows host, run `run_native_ssh.ps1` separately with
`-Arm referenced` and `-Arm unreferenced`, using new immutable run IDs.
Each invocation must originate through session-0 SSH; the script rejects a
different GUI identity or busy host mutex. Run `validate.py` for authored
assertions, then the independent read-only checker in `review/`. The
`evidence-index.json` records input, invocation, closure, event-log, report,
and all raw-file SHA-256 hashes. Raw native artifacts stay local and are not
committed.
