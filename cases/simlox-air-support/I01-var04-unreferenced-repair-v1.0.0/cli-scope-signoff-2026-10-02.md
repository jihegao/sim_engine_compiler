# I01.var04 no-task-reference ItemRepair — bounded CLI sign-off, 2026-10-02

**Decision:** Accept the observed activation of one unreferenced LRU
`ItemRepair` row under `APID=AIR_NONE`. This does not accept a complete
`<NONE>` reorder/procurement path or the task-referenced control's failed-item
disposition. Keep Issue #18 open.

## Source and execution

- Accepted stock foundation: I01.var01 source SHA-256
  `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`.
  Restricted direct source parent: I01.var05 AIR_NONE SHA-256
  `7dffc0b82a406761f55e1171491dfe9759c22c0123e2397aae4d19d6af7ba286`.
  The referenced arm is byte-identical to that parent. The unreferenced arm
  SHA-256 is `7873f467594ef1cc2bf65da25b75dbbb3d53769be73cb0196d1eec34a1ce5768`.
  Exact diff SHA-256 is
  `d5171c4a186cfd546af64d597e0e35066c07e984bbd6777a9ca86602009ff160`;
  contract SHA-256 is
  `9a639573670739112b1b84c99b6590c7a774657cca2c8972e5232c7feb70905f`.
- Only `ItemRepair.DIRPTID` changes from `I01-LRU-DIRP` to null, plus
  ProblemDescription. Both arms retain `APID=AIR_NONE`, task category/level
  metadata, the `<NONE>` MaintenanceAllocation, one local spare, seed,
  aircraft and schedule. The installed manual pp338–339 describes the
  no-task-reference repair rule. Independent pre-run static review passed.
- Two fresh guarded session-0 SSH runs, host mutex, GUI PID13340 preserved,
  five native/check steps per arm, 23/23 authored-table roundtrip, converter
  errors0, valid SXO/report, and 12 SHA-256 sealed raw files per arm.
  Author replay passes 23/23 checks. Independent read-only replay passes
  1,974/1,974 checks with verdict
  `GO_BOUNDED_UNREFERENCED_REPAIR_NO_GO_FULL_NONE_REORDER`.

## Observed result and limit

Both arms have the same h9.8829 mounted-LRU failure and first mission abort,
spare issue h10, aircraft readiness h10.5, two later mission successes and
terminal aircraft ready1. In the task-referenced control, failed LRU ID1
arrives at h10.1667 without a DIRP or stock return; the native log reports
warning #241 and local stock stays level0. In the unreferenced arm, the same
failed item starts a one-hour DIRP at h10.1667, completes at h11.1667, and
returns to local stock level1; warning #241 is absent. The three business
report tables are equal across arms, with 72 aligned System and Stock bins.
Individual event and stock logs establish the changed item path.

This finding is limited to one LRU at a WS base with one seed and no
`ItemReorder` row. Other no-task-reference rows, category/level/station
filtering, complete `<NONE>` procurement, final physical conservation of the
referenced arm's failed item, StationVariant, GUI visual behavior and
cross-engine parity remain unverified.
