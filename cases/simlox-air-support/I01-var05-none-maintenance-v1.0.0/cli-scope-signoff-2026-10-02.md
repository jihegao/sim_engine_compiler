# I01.var05 `<NONE>` maintenance allocation — restricted diagnostic sign-off, 2026-10-02

**Decision:** Publish only the warning-bearing observation that `<NONE>` suppresses the task-referenced LRU direct repair in this one model. **Do not accept** a complete I01.var05 reorder, discard, resolved item-disposition, or item-conservation claim. Keep Issue #18 open.

## Frozen lineage and execution

- Accepted I01.var01 stocked parent source SHA-256 `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`. Matching source `7c4bcb526c5e4c124a8242db97bbd140b1f7bdfc61ec72e21ff28ebf3d6e27c6`; `<NONE>` source `7dffc0b82a406761f55e1171491dfe9759c22c0123e2397aae4d19d6af7ba286`; exact diff `8661a9f153f90720a677fd9ee1aef644cb4dd7e44969274bf7880f8578834359`; contract `cad9dff29aba2ed75b62c2825732b1f1131db50c13fdee138a4c8610c4cd3e18`.
- Parent-to-model adds TaskCategory, TaskLevel and MaintenanceAllocation, references a direct-repair task from ItemRepair, and holds stock quantity one at both POINTs. Matching-to-`<NONE>` changes only Control.APID and description. Installed manual pp339/440 documents `<NONE>` repair inactivation and an ItemReorder route, while pp343–345 restrict valid reorder rows to DU/PRU/DP/SPRU items at DEPOT/STORE stations. This model has neither a valid reorder item/station combination nor ItemReorder rows. Independent pre-run static review allowed a diagnostic, not a preaccepted reorder outcome.
- Two serial guarded session-0 SSH runs preserved GUI PID13340 and completed import, export, calc, JSON report and checker; 23/23 authored-table roundtrip, converter error0, valid SXO/report, 12 sealed raw files per arm. Author restricted replay passes 23/23 and independent read-only replay passes 1,971/1,971 for the restricted observation; both reject a full reorder/item-disposition claim.

## Observed boundary

The arms have the same h9.8829 mounted-LRU failure, first mission abort, spare issue h10, system replacement/ready h10.5, later two mission successes and terminal aircraft ready1. In the matching arm, failed LRU ID1 receives direct repair h10.1667–11.1667 and returns to stock level1. In the `<NONE>` arm, the failed item arrives h10.1667 but no item DIRP, stock return or reorder is logged; local stock remains level0 after spare issue, and the native run emits warning #241 for incomplete item repair. Final disposition of the failed LRU is unresolved. Both 72-bin System/Stock reports reconcile aircraft behavior and match each other, but do not capture this physical inventory difference.

This is a restricted `<NONE>` suppression diagnostic at one station, seed, item and task. General task-category/level/station filtering, working reorder/procurement, no-task-reference activation, StationVariant, GUI visual behavior and cross-engine parity remain unverified. The earlier I01.var03 missing-category error #2038 remains an unpublished separate diagnostic.
