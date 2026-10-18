# Read-only acceptance replay

From this package directory, use Python 3.12 and the evidence-index SHA256 recorded by the independent delivery review:

    python -B replay_archived_native01_v2.py --evidence-index-sha EXTERNALLY_REVIEWED_INDEX_SHA --binding-sha a88583860620cbff6ce5bcab4fbe7bbdf2969e0ab02c197676c000489b4fa4a5

This verifies delivered artifact bytes, both complete nine-file archived raw sets, the complete typed export, DTIM binary64 and the original physical-path log contract. It does not launch SIMLOX, reproduce operating-system identities or NTFS seal attributes, or grant publication/native permission. Original absolute paths inside frozen evidence are provenance, not destinations for replay.

Delivery replay v2 parses Windows-authored component paths independently of the host and uses Windows semantics for the original log provenance. It checks complete log bytes, including every CRLF and the final terminator, allowing only the declared path and elapsed value. Run `python -B test_archived_replay_v2.py` for the exact archived-log terminator rejection controls. The frozen check_exchange_v2.py, exchange_logs.py and original replay remain historical evidence; their host-path and splitlines limitations do not define the corrected delivery validator. Source/model/oracle/raw bytes are unchanged.

Fresh native reproduction needs a new unused run target and newly bound guards and independent permissions. Never execute a consumed historical manifest/run ID. New parameter-derived-model validation and whole Issue18 reproduction/delivery remain separate requirements.

The evidence index and raw acceptance receipts preserve their prepublication publication_GO:false fields. Publication is established separately by staged/exact-remote and actual postmerge receipts; those fields must not be retrospectively rewritten.
