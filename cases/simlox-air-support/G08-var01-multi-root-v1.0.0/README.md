# G08.var01 independent second root

This case completes a bounded single-root/multi-root contrast for G08.var01. It starts from the accepted [A-root NBREQ1 control](../G08-var03-nbreq-boundary-v1.0.0/cli-scope-signoff-2026-10-03.md), with A→B/C/D. The child adds healthy physical positions E and F, each with the same LRU and G04-OPS mode, and a second independent tree edge E→F. The [exact diff](exact-diff.json) lists the five changed tables; B/A failures, rates, mission, seed, repairs and NBREQ1 remain fixed. The installed manual allows one or more roots and evaluates complete root-to-leaf paths.

B fails noncritically at h8.62763 in both control and child. A fails at the same h16.7498: the control becomes critical and aborts, while the child remains noncritical and succeeds at h34. Frozen source defines E→F as the surviving required path; the native event log reports system criticality and outcome but does not label that path. Both child CM tasks finish h34.5.

The guarded session-0 SSH native run had zero converter errors/notes, reviewed warning #108, an exact 23-populated-table roundtrip, and 72-bin System/Stock reconciliation. The [evidence index](evidence-index.json) seals 13 raw local files. [Author replay](author-validation.json) passes 83/83, and [independent replay](review/independent-validation-2026-10-03.json) verifies the bounded result separately.

This adds one healthy two-node root path at NBREQ1 under one seed/replication. Failure of E/F, arbitrary multi-root thresholds or interactions, online maintenance, GUI drawing, population reliability and cross-engine behavior remain open.
