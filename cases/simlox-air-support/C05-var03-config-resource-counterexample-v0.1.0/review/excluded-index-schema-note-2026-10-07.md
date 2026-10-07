# Excluded publication-schema draft

The first counterexample evidence index passed the package-specific byte gates but lacked a top-level `source` list recognized by the repository's published-source byte audit. It is excluded from publication; this is an index-schema defect, not a native result failure. The first publication-entry draft also used `reusable_published: false`, which left the bounded counterexample publication state ambiguous.

Preserved exact drafts:

- `excluded-index-schema-draft-2026-10-07.json`: 33,631 bytes, SHA-256 `92ec81f5ad87e392dc44718a5dc5acc83579da047e27d8fbed12d92dba8952e0`.
- `excluded-index-builder-draft-2026-10-07.py`: 10,297 bytes, SHA-256 `584fc4971423491d0edce2fd4ff627ceb637300f041f907198f4b355ad84b7c3`.
- `excluded-publication-entry-draft-2026-10-07.json`: 811 bytes, SHA-256 `fa79e1d56c9aadf8eb781cc14d882c13ee8ce504466f8e75dbfe0561aa2251ec`.

The corrected index must combine the new package and historical publishable source pins into package-relative `source` records. Historical raw and installed runtime references remain separate. The corrected entry may publish the narrow counterexample while explicitly retaining the original positive pair's `NO_GO_FROZEN_PAIR` and absent radio arm.
