# Current-target source provenance repair

Use independent-postpublication-reader-v4.py for current-target validation.
All earlier readers, guides, source snapshots and receipts remain unchanged.
Original PR544 publication is57e7ff434c5308fb18cc998d62f9940c3e856bad,
tree d1d1c757b8f41b899237975bc20e1777cf57d523. PR546 was independently
confirmed merged as11a6b21ecaf4e0d6a3817763585eebc418f40996,
tree ff49f7a92633b78e2727c00253587a7a56c59cac, parents21b9ad44e956fd29eb4bebfc8236a5c5af1564b0
and48cbeb30301baecc8a03fb6f102f8f40395fbe7f. Its controller review covered
offline repair contracts; it did not perform host-bound original raw replay.

v4 preserves the actual published v3 implementation: isolated Python child,
captured source/binding/code buffers, fixed module pins, the original four
publication replacements plus five approved captured-source replacements,
captured-module preload, entry wrapper capture, terminal
path custody, payload/bootstrap/code receipt hashes and15/120-second Git/raw
timeouts. Published helpers/protocols remain unchanged. Additive v4 helper and v3 protocol use
exact reviewed replacements and capture input/manifest data alongside executed code.
The isolated bootstrap validates fixed hashes, exact payload keys and unique
canonical data/code paths before execution. Parsing, hashing, direct byte checks
and size checks consume those captured anchors; the raw reader reports exact
captured input/manifest hashes and executed-reader hash, checked before outer GO.

Current-target additionally verifies the frozen input, prelaunch manifest and
inherited reader Git blobs at the explicitly selected actual target commit.
Altered or missing anchors reject before any subordinate launch, even when
commit/tree and original ancestry are valid. source_provenance records original
and current commits and these three SHA256 anchors. This is a three-anchor
contract, not a claim that every historical external role is a target Git blob.
Historical-publication verifies original publication/source/raw identities,
permits subsequent remote target source evolution and index appends while the
local original frozen source snapshot remains unchanged, and never reports
current-target acceptance. An evolved local source checkout explicitly fails
LOCAL_SOURCE_MISMATCH in either mode; use the preserved frozen local snapshot.
Exclusion and historical evidence are not new passes.

From the package directory:

```powershell
python -X utf8 -B review/test_publication_target_v1.py
python -X utf8 -B review/test_publication_artifact_snapshot_v2.py
python -X utf8 -B review/test_publication_artifact_snapshot_v3.py
python -X utf8 -B review/independent-postpublication-reader-v4.py --target-binding C:/verified-actual-target.json --product-binding C:/verified-product.json
python -X utf8 -B review/independent-postpublication-reader-v4.py --mode historical-publication --product-binding C:/verified-product.json
```

The60 preserved tests and31 v4 tests are91 test executions, with overlapping
custody coverage; this is not91 distinct simulation conformance requirements.
The new suite includes altered/deleted selected-target anchors for all three
sources, no-child negative controls, future-source historical positives, source
ABA/same-buffer derivation, module/code/binding custody and actual isolated
bootstrap shadow/tampered/missing/duplicate-key tests, captured-data replacement
and deletion controls, child data/reader claim rejection and duplicate canonical
path controls. Historical positives cover evolved remote sources with a preserved
local snapshot; explicit evolved-local-source negatives cover both modes. Complete existing raw
readonly replay is separate evidence:115 loglines,4044 typed report cells/full
metadata,33 tables,72+72 bins, start-registered ledger/endstate,140 source roles
and25 original/recovered readonly pairs. No native run or parent/child rerun.

Explicit expected target/product artifacts must come from independent official
commit/tree/ref provenance, not a mutable-tip default. The original frozen
binding continues to identify PR544. After a follow-up merge, use a new external
actual-merge binding; do not overwrite old bindings or embed the validator's own
merge hash in its source. Job receipts bind the actual follow-up commit/tree,
reviewed blobs, artifact SHA256 and full raw results without circular identities.

This adds five files only. The57 previous case files plus the publication index
(58 protected published blobs), frozen originals,
failed drafts and raw evidence remain literal unchanged. Publication metadata
stays513 packages/107 IDs; effective nonGUI denominator remains null. GUI-exclusive
validation is excluded; no engine/IR/RunState/case rules change, no cross-engine,
performance, whole-variant or whole-Issue proof. CI failures remain separate
unverified evidence until their actual cause is established. Overall Goal stays active.
