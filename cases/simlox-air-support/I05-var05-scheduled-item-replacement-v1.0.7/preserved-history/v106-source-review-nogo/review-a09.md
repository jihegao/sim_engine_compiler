# Independent source review A09: v1.0.6 NO_GO

Decision: NO_GO_SOURCE_ONLY for frozen source-freeze.json (45,019 bytes, SHA-256 2b2db3b8e2965b25b5b9389bcde79dcc4fd292cbde99731954619e087499c9b5). All 101 listed local/external files matched bytes, SHA-256 and Windows attributes; 12 accepted-parent raw pins matched; v1.0.6 run path, preflight and approval were absent.

Blocking omission: active publication-index-v1.json is 548,720 bytes, SHA-256 2aa600b129a1b725ca161b3f7cf43ac654e108376be393e4fb93b952b2d5e085 and contains exactly one accepted H02.var04 parent entry. Freeze and both source/manifest generators bound only catalog-v2.json, not this authoritative publication index. Parent publication could change without invalidating source or preflight custody. No checker, SSH, preflight or native command was run; no candidate files changed.
