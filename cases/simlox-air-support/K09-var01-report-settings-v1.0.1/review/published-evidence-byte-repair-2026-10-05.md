# K09.var01 published evidence-byte repair — 2026-10-05

The existing v1.0.1 evidence index pins source bytes from both the excluded v1.0.0 diagnostic and the accepted v1.0.1 report-only run. Git's inherited text attributes converted four pinned local files from CRLF to LF on publication: `run_reports_ssh.ps1` and `review/independent-verdict.json` in each version. The same conversion affected the v1.0.1 evidence index itself, although that index has no self pin. File content and parsed verdicts did not change.

| Version and file | Original local/index SHA-256 | Previous Git SHA-256 |
| --- | --- | --- |
| v1.0.0 runner | `e4434cdb031aae2e8937db9b057e64d69318e2f45741d7943f93bb5c8a1eaad8` | `de1237728bdae8e4b424144f91a93e61d64fcaf03b7db90fa590f0457b94d370` |
| v1.0.0 verdict | `6011b8e767374cbad87d92ffc37344baf44e92343c166b3fa4cdd6c87efc616e` | `8a72d28418f77e420e92578a58cd6636ae71404c303e9e1d590fc54c34d22653` |
| v1.0.1 runner | `f106bb879d11a9b6f7a7690b02a1e08da00bcec19643afebd5156857b8231504` | `dedf42c65db37d336c63df558308fa28750508caf4f106126544df6a8acd7f70` |
| v1.0.1 verdict | `081a7fb7e8fc9ff449601dd574572c3bb5de2f054150197c25562a82d172211b` | `bb99d9f04970a9698384ecc7abd2d3010d4caeed85f009a8e4fee88d0df3d3c7` |

The exact-path `.gitattributes` overrides preserve the original CRLF byte sequences in Git. Both packages retain their general `*.json text eol=lf` rule for other JSON files. The pre-existing evidence-index file and every old pin remain unchanged in content; the index is staged with its original local bytes. The four pre-repair Git blob hashes above remain available in repository history.

The local audit found exact staged byte matches for all **10/10** v1.0.1-indexed source entries, the index itself, and **16/16** raw SHA-256/size seals across the diagnostic and accepted runs. No native call, accepted behavior replay, raw artifact edit, or claim expansion is part of this repair.
