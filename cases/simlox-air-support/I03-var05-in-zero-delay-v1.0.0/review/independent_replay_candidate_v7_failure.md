# Independent reader candidate v7 failure

`independent_replay_candidate_v7.py` is 33,180 bytes, SHA-256 `3112068d02d0e69941b5f5750aef508f53dc8d739734ceb0b947ec986b423da9`. Its first pure run after adding documentary custody failed before any native semantics because it treated `source_lineage.required_docs` as a one-element list of eight records. The frozen v4 contract stores it as one eight-key JSON object. The correction changes only this auditor schema read. The traceback exists as a command tool transcript, not captured original stdout/stderr bytes. No native or author source changed.
