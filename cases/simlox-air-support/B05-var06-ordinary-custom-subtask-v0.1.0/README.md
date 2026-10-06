# B05.var06 ordinary custom subtask v0.1.0

This package classifies the ordinary `INSPECT` arm of the [accepted B05.var03 contrast](../B05-var03-predefined-inspect-v1.0.0/README.md) for the catalog's B05.var06 question. It reuses that arm and its `<INSPECT>` contrast; it creates no input or native run.

The ordinary source defines `INSPECT` and `SERVICE` in `SubTaskType`. Its `TaskBreakDown` references `INSPECT` for PREP-FIXED SEQ1 at 1/6 hour and `SERVICE` for SEQ2 at 1/3 hour. The contrast changes the description and SEQ1 identifier to predefined `<INSPECT>`; source and native export bind the exact identifiers. Both guarded SSH session-0 runs perform SEQ1 h7–7.16667 and SEQ2 h7.16667–7.5, launch at h8, succeed at h10, and end with one ready aircraft. All summary, 72 System and 72 Stock report rows match across the pair. The native event log uses generic subtask labels, so the identifier claim depends on the sealed source and exact authored import/export roundtrip.

Run `python check_reclassification.py` for the author read-only verification. The separate reviewer script and verdict in `review/` replay the source and native evidence independently. The [evidence index](evidence-index.json) pins new review sources, all 16 accepted source files at both disk and published Git byte identity, and both original run closures and their 24 local raw seals. No raw run copy is published.

This is one fixed-seed mission preparation comparison. It does not test other ordinary identifiers, task categories, resource requirements, GUI visuals, cross-engine behavior, or the full B05.var06 and Issue #18 questions.
