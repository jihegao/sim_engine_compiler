# Independent staged publication review — 2026-10-07

**GO_STAGED** for the bounded C09.var02 retrospective ordinary-control publication. This decision covers the exact current Git index and does not authorize a native run or claim the prospective TTRSS pair passed. The v1.0.2 pair remains **NO_GO_PROSPECTIVE_PAIR**; the shortage arm was never started.

## Exact staged scope and pins

- The Git index contains **105 intended paths only**: 101 frozen standard-index source files across the five C09.var02 packages, the v0.1.1 `evidence-index.json`, two excluded-prefix independent content-review artifacts, and one appended root `publication-index-v1.json`. The independent read-only `review/independent-staged-audit.py` (4,835 bytes; SHA-256 `ff3662fc9d099ef74c1cd60e9fd6bbd84ead841ed9c1b003040de5c1e54b205b`) compared the complete staged path set, every indexed source’s **working bytes and staged Git blob** with its SHA/size pin, and the staged evidence index with disk. No run directory, proprietary binary, product runtime file or unrelated path is staged.
- Frozen evidence index: 80,078 bytes, SHA-256 `c76f768942de24e9733e61e5dcf44755430fe5b910593f842710588536d3ff50`; its 101 standard source records and 130 local raw records match exact SHA and size. The raw set is 117 accepted dependency files plus the 13 sealed failed ordinary-run files. All nine accepted dependency closure/invocation chains and the sole failed ordinary closure/invocation/failure chain were checked in the prior independent content gate. The 77 accepted source references match the pinned base Git blobs separately from local bytes; D03 `.gitignore` and `parent-diff.json` are the two legitimate disk/Git-distinct identities. No normalization was used.
- The accepted v0.1.1 contract remains SHA-256 `2abc4d733557d97c0766c88599429cef756fcdf16315db56102076670c96632b`. The indexed independent verdict `5ebe43374a550d330dc8d70316f0f0761e026cb660037f1ef05a0b822c446651` reports all 1,754 report cells reconciled and 26 semantic tamper rejections, including a full-comparison exact-zero FTMO `0→1e-9` probe. The author self-check records 23 rejections and two within-bound accepts. Earlier unapproved contracts, prospective failure and first independent replay bytes are staged as explicitly classified historical evidence. The source, guide, signoff and catalog entry retain `positive_pair_accepted:false`, `new_native_runs:0`, and `shortage_arm:not_started_not_tested`.

## Root catalog identity

The preserved pre-append catalog has 485 entries. Parsed metadata and those first 485 entries are unchanged in both the working and staged 486-entry catalog; the unique 486th entry equals the package’s exact `publication-entry-v1.json` and has resolvable package/evidence/guide/contract/signoff paths. Old and new **disk and Git blobs are distinct byte identities**, as expected from the root catalog’s line-ending policy:

| Catalog identity | Bytes | SHA-256 |
| --- | ---: | --- |
| Old disk backup | 481,953 | `0962583e83bb8838b31592db142cbbb87ba678dcf527ac41bdf701352354ef8a` |
| Old HEAD Git blob | 481,388 | `dc453949203c10ee7032e4d80eff23526cf5840acddb616e3b06147a2d07caf9` |
| New working file | 483,289 | `8e403bf64ffc068a5ccd6092214da2ccd9626205c33d8722b6dd348a1af36ad1` |
| New staged Git blob | 482,723 | `e8d50785f23c2458b86395bd782c109c691dc8aa132ae977fe374702c6411f17` |

The CR-aware `git diff --cached --check` reports only one blank line at EOF in `physical_ledger.py:107`. That frozen file’s disk and staged Git bytes match its evidence-index pin; no content repair or normalization was made. No other whitespace diagnostic appeared.

The package evidence index remains at content-ready status until root publication. This memo is deliberately excluded from that self-sealed index; it should be staged as an additional reviewed file only after its SHA is recorded. Remote PR review and merge remain separate gates.
