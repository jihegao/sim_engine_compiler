# Factual correction to the preserved publication-draft NO_GO

The preserved `review/independent-publication-draft-no-go-2026-10-07.md`, SHA `5a37dc260c5f9fc7a794521ee3902821a8584d6d686a5706036e0627133cdb80`, incorrectly states that the rejected index pinned `make_evidence_index.py` to SHA `6117a489...` and was internally stale. That statement came from a read during active author mutation and is withdrawn.

I reopened the exact preserved `review/excluded-index-schema-draft-2026-10-07.json`, SHA `92ec81f5ad87e392dc44718a5dc5acc83579da047e27d8fbed12d92dba8952e0`. Its `source_files["make_evidence_index.py"]` record is **10,297 bytes, SHA `584fc4971423491d0edce2fd4ff627ceb637300f041f907198f4b355ad84b7c3`**. The preserved `review/excluded-index-builder-draft-2026-10-07.py` has exactly that SHA. There is no demonstrated builder-pin mismatch in the rejected snapshot and no requirement to recover `6117a489...` bytes.

The original NO_GO decision remains valid for its other two reasons: `source_files`/`historical_source_files` were invisible to the repository's generic published-source byte auditor, and the first entry's `reusable_published: false` wording ambiguously described the intended bounded reusable counterexample. Keep this correction and the original memo together as review history; assess the corrected index and entry on their own exact bytes.
