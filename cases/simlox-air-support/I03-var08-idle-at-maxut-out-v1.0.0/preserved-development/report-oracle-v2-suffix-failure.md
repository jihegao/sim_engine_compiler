# Second report parser draft: CRLF normalization omission

The second draft source `report-oracle-v2-suffix-draft.py.bytes` is 7,453 bytes, SHA-256 `31c403f504051b451e99c000a65b24cbc3fbe5f36e4a3287a36a3d53a568aadd`. Its read-only parent probe exited 1 and displayed a decoded `AssertionError`; original process stdout/stderr bytes were not captured.

The accepted raw report has CRLF line endings. The draft decoded raw bytes directly and checked an LF-only suffix before its one-comma in-memory repair. The corrected parser will check/normalize CRLF in memory after the original raw SHA check, then apply only the one declared trailing-comma repair. No original report or prospective oracle value is changed.
