# E14 published review-byte repair — 2026-10-05

The previously published E14 v1.0.0 evidence index pins the original local review JSON bytes. Git's inherited `*.json text eol=lf` attribute converted only two CRLF review files to LF when they were committed. Their parsed JSON remained equal, but their Git blob lengths and SHA-256 values did not match the existing index.

| Review file | Original index/local bytes and SHA-256 | Previously published Git bytes and SHA-256 |
| --- | --- | --- |
| `author-validation-2026-10-05.json` | 2,870; `2ac29592f82213285c724983cf7aefc8efcf1298503f6761287b5936f88a1b8f` | 2,738; `df0eda5b1b81b417e555062385ae4fd65baf6af79a3c99643a59802b1c2fc347` |
| `independent-verdict.json` | 9,357; `2c6f4d08c1a54fb10879bc854ac745ff6d1907195687766b7f881fcd8bec14d3` | 9,042; `b919e8312d9a4704cf3686d22f2df04d48d94d431f4cf40151e5068e8564f90d` |

The adjacent `review/.gitattributes` disables text and EOL conversion for those two exact paths. Restaging their unmodified local files stores the original byte sequences in Git. The package's original `.gitattributes`, existing evidence index, native inputs, contracts, runners, review JSON content and raw artifacts are unchanged. This repairs the published source-byte binding; it does not rerun or broaden the accepted joint RRF/NFFF behavior.

The pre-repair inspection reported equal parsed JSON and exact CRLF-to-LF conversion for both files. The post-repair local audit matched **23/23 existing evidence-index source entries** against staged Git blobs and **164/164 local raw SHA/size seals** across both runs. The original evidence-index file is not part of this patch; its pins remain authoritative. Independent review and PR file-scope checks precede merge.
