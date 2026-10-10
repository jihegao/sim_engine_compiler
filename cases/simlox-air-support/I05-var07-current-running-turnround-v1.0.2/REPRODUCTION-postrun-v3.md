# P1/P2 current reproduction entry

This additive v3 guide supersedes the postpublication commands in the preserved
v1 and v2 guides. Original PR544 publication remains commit
57e7ff434c5308fb18cc998d62f9940c3e856bad/tree
d1d1c757b8f41b899237975bc20e1777cf57d523. Initial P1 repair PR545 was actually
merged as21b9ad44e956fd29eb4bebfc8236a5c5af1564b0/tree
a17d612387ffeaa3b48b46f487729d54fd6fe7e2; this fact and its completed original
raw replay remain evidence despite the subsequent P2 artifact-fingerprint defect.
All old readers, guides, binding, source snapshots and receipts remain unchanged.

PR545 P2 thread4237866740 showed that v2 parsed external target/product JSON early
but reread their paths to calculate receipt hashes after the long raw replay.
A replacement could associate a GO with unvalidated bytes. Use v3 instead:

```powershell
python -X utf8 -B review/test_publication_target_v1.py
python -X utf8 -B review/test_publication_artifact_snapshot_v2.py
python -X utf8 -B review/independent-postpublication-reader-v3.py --target-binding C:/verified-actual-target.json --product-binding C:/verified-product.json
python -X utf8 -B review/independent-postpublication-reader-v3.py --mode historical-publication --product-binding C:/verified-product.json
```

v3 captures each original publication, explicit target and explicit product
artifact once. Its duplicate-key-rejecting parse and recorded SHA256 use those
same bytes. Immediately before GO it requires each path still contain exactly
the captured bytes; replacement, deletion or a whitespace-only change rejects
with nonzero exit. A changed artifact produces BINDING_ARTIFACT_CHANGED; deletion
produces explicit file-error NO_GO. No GO is forwarded from the raw helper.

The v3 subordinate receives the parent's already captured original binding via
binary stdin, verifies its immutable SHA256 and parses those same bytes through
publication_snapshot_v2.py. It never reopens the binding path. A temporary
replacement followed by restoration therefore cannot change the subordinate's
commit/path/hash or published index. The exact four-change derivation from v1
retains the three reviewed v2 changes and replaces only the subordinate binding
load with this captured-byte protocol. Published v2 helper/module remain untouched.
Additional tests exercise actual captured-input handoff, replacement/restoration,
missing/wrong stdin payload and exact helper derivation. The first unpublished
PR546 candidate is preserved with its original commit/three-file SHA closure.

PR546 review4238002765 additionally identified a late local module import ABA.
The final parent captures the exact derived reader and both local modules before
launch, requires fixed reviewed module SHA256 pins, and sends their bytes plus
the original binding in one stdin execution bundle. A standard-library-only
bootstrap validates these bytes against trusted hashes embedded in its command,
preloads captured modules in sys.modules, and executes the captured reader code.
It never opens local module or reader paths to load executable code. The original
four-change reader derivation and all original raw assertions remain unchanged.
Receipt code hashes use captured bytes; all captured code paths must still match
before GO. The subordinate's inherited path-based reader hash is historical
metadata; executed-code identity is the parent's captured snapshot_reader_sha256.
The previous five-file b2e69449 candidate and its helper-module NO_GO are retained.
There are53 pure tests (34 original plus19 artifact/code custody regressions),
including actual bootstrap tampered/missing code and binding rejection, fixed
module-pin and duplicate execution-key rejection before child launch, and ABA
of both modules and the reader.

The explicit artifact schemas, origin/repository/source/version/commit/tree,
original publication/product ancestry, immutable original513-index snapshot,
all140 source roles/25 readonly pairs and before/raw/after actual refs have exactly
the v2 contracts documented in REPRODUCTION-postrun-v2.md. The default still
requires original PR544 current target and original product commit; it deliberately
rejects their independently established subsequent advances. Never infer expected
commit/tree from a mutable observed tip. Actual follow-up merge bindings remain
external independently verified job artifacts, preventing circular self-binding.
Historical-publication output is distinct from exact-current-target publication.

v3 adds artifact custody only: no native calls, reruns, case development, engine,
IR, plan, RunState, source/oracle/index changes or package-count increment. Pure
replacement tests are validator regressions; full existing original raw readonly
replay supplies the separate bounded behavior evidence. GUI-exclusive validation
remains excluded, nonGUI denominator null, and whole Issue/Goal unfinished.
