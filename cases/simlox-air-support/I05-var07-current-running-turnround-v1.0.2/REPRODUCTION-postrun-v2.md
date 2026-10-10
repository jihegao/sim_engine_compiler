# P1 repair: publication identity and original readonly replay

This additive guide supersedes the v1 postpublication command in the preserved
REPRODUCTION-postrun.md. The v1 reader remains byte-identical historical evidence:
it checks product main but does not validate simlox/main, so its GO alone cannot
prove remote publication. PR544's independently established actual merge remains
`57e7ff434c5308fb18cc998d62f9940c3e856bad`, tree
`d1d1c757b8f41b899237975bc20e1777cf57d523`, parents `d2d6e6f...` and `cd06eec...`.
The original source/version/ref/commit/tree/full parents, input, frozen manifest,
v1 reader and committed publication-index fingerprints are recorded in
`review/publication-binding-v1.json`. The v2 entry validates that binding's own
SHA256 before using it. No native execution or parent/child rerun is required.

Use the installed Python on4700-3 with the retained host-bound job/source/manual
and 25 readonly original/recovered pairs. Do not run with `-O` or `-OO`; v2 rejects
disabled assertions. From this package directory:

```powershell
python -X utf8 -B review/test_publication_target_v1.py
python -X utf8 -B review/independent-postpublication-reader-v2.py
python -X utf8 -B review/independent-postpublication-reader-v2.py --mode historical-publication
```

The default **current-target** command expects exactly the original PR544 commit
AND tree on actual `origin` ref `refs/heads/simlox/main`. Missing ref, parent-only
target, wrong commit/tree, wrong repository/source/version/provenance, missing Git
objects, raw mismatch, or disagreeing before/raw/after ref observations rejects
with nonzero exit and `NO_GO_POSTPUBLICATION`. Only after all identity and full raw
checks does it emit `GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY`. Product
`refs/heads/main` defaults to `a1a44c72f64d754b711abe4095f1111f8a5ba896`.
An external legitimate product advance is not an edit by this validator. The
default still rejects it. An optional `--product-binding C:/verified-product.json`
works in either mode only with schema `simlox-expected-product-reference/v1`, the
original `publication_binding_sha256`, repository `jihegao/sim_engine_compiler`,
remote `origin`, ref `refs/heads/main`, explicit expected `commit` AND `tree`, and
nonempty official `provenance` and `independent_receipt` locators. The actual
product ref/tree must match, the original product commit must be its ancestor,
and all observed refs must stay identical before/raw/after replay. No automatic
rebinding or product branch writes occur. During independent repair review,
external PR542 advanced product main to `0f1d4a108db2c9200c2d4724383bfb067bed08eb`,
tree `ab5a7a31535edc722ca071d54bacbc0770c837a7`, with the original product commit
as its first parent. The preserved initial NO_GO records that external change.
Supply its independently verified product artifact for current full replay.

After a valid later merge advances simlox/main, the default intentionally rejects
an exact-current-target claim for the old commit. For verifying the new current
target, provide an **explicit independently verified** external JSON artifact:

```powershell
python -X utf8 -B review/independent-postpublication-reader-v2.py --mode current-target --target-binding C:/path/to/verified-target.json
```

The target artifact uses schema `simlox-expected-publication-target/v1`; contains
`publication_binding_sha256` equal to the shipped binding's fingerprint; copies
its `repository`, `remote`, `ref`, `package`, `case_version` and `run_id`; specifies
the expected actual new `commit` and `tree`; and includes a nonempty `provenance`
locator to the official merged PR and independent receipt. Do not infer those
expected values from the observed tip or auto-rewrite the original binding.
The validator requires exact ref/commit/tree agreement and original PR544 merge
ancestry. A repair PR cannot embed its own eventual merge SHA/tree in its prior
source tree: its verified external target artifact belongs in the repair job.

The explicit **historical-publication** mode instead validates original PR544's
immutable commit/tree/parents and source blobs, then requires that original merge
remain reachable from the observed current target. It records current ref/tree
as observations, not an expected current publication binding, and emits only
`GO_BOUNDED_HISTORICAL_PUBLICATION_READONLY_REPLAY`. It never substitutes for the
exact current-target publication gate. An unrelated branch or parent-only target
rejects. Supplying a current-target artifact to historical mode rejects ambiguity.

`original-published-snapshot-reader-v2.py` is an additive derivation of v1 with
exactly three reviewed replacements: read the publication index from the bound
original Git commit rather than the mutable live index; label its subordinate GO
as raw snapshot replay only; remove only the inherited fixed-product assertion,
retaining its actual ref capture for the outer explicit product/ref/tree/ancestry
gate and race check. The helper supplies raw evidence only; the outer validator
enforces all publication/product claims. The outer entry verifies the derivation and
captures its output. The old remote-unbound GO is never forwarded. The original
513-entry index snapshot remains fingerprinted; a later valid 514+ live append
does not change an old bounded replay. All 115 ordered CRLF events, 4044 recursively
typed report cells/full metadata, 33 native/default tables, 72+72bins, registered
start ledger/endstate, 138 literal plus2 exact archived source roles and all25
readonly pairs retain the original assertions and SHA256 custody checks.

Git object/ancestry inspection is readonly, uses `--no-replace-objects`, and does
not fetch or edit refs/configuration. Missing local Git objects fail explicitly;
prepare them separately through normal approved Git operations if necessary.
Pure tests simulate only publication observations, not native conformance.
Existing full raw readonly replay supplies the separate behavior evidence.

This repair changes publication validation only. No engine, Business/Core IR,
Execution Plan, RunState, model, oracle, original/failure evidence or live
publication index changes.513packages/107IDs remain metadata; nonGUI denominator
null. GUI-exclusive validation remains excluded. CI, crossengine, performance,
wholevariant and wholeIssue are not established by this repair.
