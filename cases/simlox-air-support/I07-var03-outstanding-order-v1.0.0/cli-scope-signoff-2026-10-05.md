# I07.var03 pending-order lead time: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one stock-based order
already outstanding when `ChangesItemReorder.LEADT` changes. It becomes
`reusable_published` only after merge to `simlox/main`. Full I07 and Issue
#18 remain open.

The frozen input derives from the accepted I07.var01 h5-change arm; only the
description and scheduled `TIMEC` 5→10.5 differ. The source's existing
`ItemReorder.LEADT` is one hour and its scheduled new LEADT is three. The
accepted h5-change arm and E15 explicit-three parent are reused by byte pin;
neither was rerun. The installed manual and dictionary, report selector,
executable, parent signoffs, evidence index and accepted run closure match
their source pins. Independent contract and static reviewers approved the
corrected runner before the native call. The first runner draft was NO-GO
before execution; its hashes and correction are retained in `review/preflight-2026-10-05.md`.

The fresh run `i07-var03-outstanding-v100-ssh-20261005-01` completed four
guarded session-0 SSH CLI stages under the global mutex while GUI PID13340
was preserved. The pinned pre-calc checker found exact roundtrip of all 22
authored row-containing tables. Conversion gave Errors0/Warnings1 (#108
only)/Notes0; native SXO, event log and selected report are valid and
nonempty. Its 13 local raw files are sealed by SHA-256 in the immutable
closure. The native export also has additional null placeholder rows.

At h10 the common ordinary demand issues physical DU ID0 from depot to base
and starts a two-item reorder under the initial one-hour lead. At h10.5 the
scheduled update causes no separately logged order or physical stock move.
The existing order completes at h11 and adds new physical IDs 5 and 6 to
depot stock; ID0 reaches base at h12. The late-run event log is byte-identical
to the accepted one-hour control and E15 original-order log. The accepted
h5-change arm starts the matched order with a three-hour lead and receives
the same quantity at h13. The late depot on-hand ledger is 3 before h10,
2 for h10–11, then 4; the early comparator stays at 2 until h13. All 72
half-hour selected depot bins, physical snapshots and identities reconcile;
nominal STSZ remains 4, NRO is one and backorder zero. Mission, system and
aggregate stock results are unchanged. The native log does not directly
announce application of the h10.5 row, and no later order is generated to
exercise the updated setting.

Author replay passes **222/222** checks. Its first pass caught an author
checker omission of the intermediate stock snapshot after ID5 arrived;
the diagnostic is retained and the corrected replay leaves native bytes
untouched. Independent read-only replay passes **2,360/2,360** checks and
confirms all raw seals, accepted comparator bytes and full event/report
ledger. This acceptance covers one pending order, one fixed seed and one
mid-order lead-time update. It does not establish a later order, interval
policy, multiple outstanding orders, random lead, tie-time change, GUI,
cross-engine equivalence or full I07/Issue #18 behavior.
