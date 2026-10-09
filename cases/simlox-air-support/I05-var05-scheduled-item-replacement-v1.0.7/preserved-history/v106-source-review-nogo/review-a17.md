# Independent static review A17: v1.0.6 NO_GO

Decision: NO_GO_SOURCE_ONLY_AS_FROZEN for source-freeze.json (45,019 bytes, SHA-256 2b2db3b8e2965b25b5b9389bcde79dcc4fd292cbde99731954619e087499c9b5). All 101 listed files match byte/hash/attribute pins; v106 native path absent. Static review found no additional blocking defect in roundtrip checker, 14 adversarial tests, build, PS5 runner or SSH transport. v104 remains NO_GO and v106 replay is predicate-only.

Blocking omission: the active worktree publication-index-v1.json (548,720 bytes, SHA-256 2aa600b129a1b725ca161b3f7cf43ac654e108376be393e4fb93b952b2d5e085; attrs 32) has the accepted H02.var04 entry, but is not pinned or checked by source-freeze or manifest builder. Add exact index pin and typed parent-entry validation in a distinct version. Reviewer used read-only hash/attribute checks and source inspection; no checker, Git, SSH, preflight or native action was run; no files edited.
