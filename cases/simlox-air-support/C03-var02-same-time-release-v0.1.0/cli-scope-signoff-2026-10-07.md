# C03.var02 bounded read-only scope assessment

**Status: author and independent read-only replay GO_BOUNDED; source-byte index sealed; independent publication review pending.**

The frozen contract is SHA-256 `5c441afe4cd33bfda4a955e4df90bff442b923a40d7e3981692be609a748ba05`. Independent contract review is GO_CONTRACT_ONLY, memo SHA-256 `2adbab57984b3ef79ae5292b40710e2c9d37423260de092f0173952cdb80d627`.

The author read-only checker passed **16,582/16,582** checks on two executions with identical verdict bytes. It verified 16 accepted C03 tracked source paths with separate local/Git identities for the CRLF/LF `.gitignore`, the published C03.var01 parent pins, two accepted input/closure/invocation chains, **22** original raw SHA/size seals, 20 row-containing authored-table roundtrips per arm, the physical h8 event order, and every cell in six native report tables (**5,210 per arm; 10,420 total**). There was no native rerun.

The only source-cell delta between the accepted inputs is AIR_BASIC/P-CREW/BASE-01 `ResourceAllocation.RQTY` **1→2**. In the one-crew run, aircraft 0 releases the crew at h8; the native log then lists aircraft 1's waiting task, retests availability, records receipt and booking of that same crew, and starts aircraft 1's work at h8. Aircraft 1 releases h8.5, both aircraft launch together and the mission succeeds h9.5. The two-crew control prepares both aircraft h7.5–8 and succeeds h9. The pair's report cells differ only in 12 SystemResults, 219 ResourceResults and 4 ResourceResultsTotal cells; description, summary and stock are equal.

The separate independent replay passed **11,732/11,732** checks, reconciling both raw chains and all 10,420 report cells. Its LF verdict SHA-256 is `ec1c91a48a284469dd3e5c6b49ede62dbc0f9f666550ced2e9a76bbdb1553280`; its postrun memo SHA-256 is `64ba0d7eee8147c8237af4c1f4dc646a0ff567ea773b0304f5986f66ec110123`.

The result overlaps C03.var01 and establishes only this logged fixed-seed ordering. It does not prove a general same-time priority, fairness, release/regrant or mission deadline law, nor GUI-only behavior, alternate resource networks, other seeds, or cross-engine parity. `ResourceResults.NRA` is checked as a reported field, not inferred as the free-worker complement of `NRUM`. Independent publication review remains required.
