# A01/A02 GUI and pairing readiness

Source is the accepted `04dce604f6be75df064d40519187b482ceb4ddb8`
case-library commit and its four sealed native runs. This slice is a read-only
handoff; no engine implementation, J35 change, new native run or GUI login.

1. Freeze source hashes, native binary file metadata and all four accepted run
   references. Recompute the existing strict validator on 4700-3 without writes.
2. Derive normal-case events and 72 half-hour states from the declared contracts;
   compare each event and state with the sealed native observations. Record
   separate RCEND collection behavior and the sampled SIMPE rejection boundary.
3. Package only contracts, native input JSON, compact accepted records, expected
   observations and a portable integrity/semantic checker. The zip has stable
   paths and timestamps; delivery metadata outside the archive pins its SHA.
4. Prepare a GUI checklist pointing to existing SXI/SXO and required screenshots.
   GUI calibration/review stays pending private user handoff.
5. Run portable positive and negative checks and the existing focused native
   evidence tests. Commit only the handoff; deliver a complete Git bundle and
   archive for coordinator review on Draft PR #21.

Stop conditions: any source hash mismatch, strict bound-run recheck failure,
event/interval discrepancy, package validator false positive, or missing
artifact prevents a ready handoff. Engine equivalence is not asserted by
package integrity.
