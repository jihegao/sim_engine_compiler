# I07.var09 v1.0.0 `-02` static postrun triage — 2026-10-05

**NO-GO for the frozen full contract; retain this run as an excluded diagnostic.** The guarded run established converter behavior but contains an additional missing-value error that prevents a clean strategy-switch attribution.

The sealed run is `i07-var09-time-to-stock-v100-ssh-20261005-02`; closure SHA-256 is `f2d8b69aa92152c51d95b1811f70456eeafbaa87afe565889de9ac9e6c2ae38e`. I independently verified the invocation SHA, all ten listed raw file sizes and SHA-256 hashes, and equality of every before/after source fingerprint in the closure. The invocation records SSH session 0, `Global\SimloxIssue18NativeQueue`, and protected GUI PID13340/session1/start identity. Import, export, and calc are three exit-zero steps, each recorded with GUI preservation. The roundtrip result passes all 22 authored populated tables with no mismatches.

The converter reports Errors 2, Warnings 2, Notes 0. Both errors are under `ChangesItemReorder` record 1: #84 says reorder `LEADT` is undefined, and #375 says the `ROINT` change is inconsistent for `TEACH-DU-01/DEPOT-01`. Warnings are the inherited #108 and time-based-reorder #376. The SXO is four bytes, and there is no event log. This is evidence of a specific strategy-related rejection, but #84 is a separate, confounding defect in the authored change row. The runner correctly records `frozen strategy-switch rejection gate failed` in the outcome and closure; no report or inventory result is claimed.

The parent `ItemReorder` row has `LEADT=1` and `ROINT=16`; the child leaves that initial row unchanged and adds a `ChangesItemReorder` row with `TIMEC=5`, `ROINT=0`, but null `LEADT`. A separately frozen v1.0.1 may set the new row's `LEADT=1`, preserving the parent's lead time while testing the same forbidden strategy change. Its prospective acceptance gate should require a `ChangesItemReorder` record-1 strategy error (#375 if reproduced), no #84 or unrelated converter errors, and no usable output. This triage does not predict the fresh native outcome or promote the excluded `-02` run.

No native process was invoked during this review. No source or raw file was modified.
