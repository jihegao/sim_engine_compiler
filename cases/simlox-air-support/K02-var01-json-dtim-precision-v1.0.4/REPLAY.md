# Read-only acceptance replay

From this package directory, use Python 3.12 and the evidence-index SHA256 recorded by the independent delivery review:

    python -B replay_archived_native01.py --evidence-index-sha EXTERNALLY_REVIEWED_INDEX_SHA --binding-sha a88583860620cbff6ce5bcab4fbe7bbdf2969e0ab02c197676c000489b4fa4a5

This verifies delivered artifact bytes, both complete nine-file archived raw sets, the complete typed export, DTIM binary64 and the original physical-path log contract. It does not launch SIMLOX, reproduce operating-system identities or NTFS seal attributes, or grant publication/native permission. Original absolute paths inside frozen evidence are provenance, not destinations for replay.

Fresh native reproduction needs a new unused run target and newly bound guards and independent permissions. Never execute a consumed historical manifest/run ID. New parameter-derived-model validation and whole Issue18 reproduction/delivery remain separate requirements.

The evidence index and raw acceptance receipts preserve their prepublication publication_GO:false fields. Publication is established separately by staged/exact-remote and actual postmerge receipts; those fields must not be retrospectively rewritten.
