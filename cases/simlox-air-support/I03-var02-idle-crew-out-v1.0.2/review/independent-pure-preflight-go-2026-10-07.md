# Independent I03.var02 v1.0.2 pure preflight decision

**GO_PURE_PREFLIGHT**, limited to one actual SSH5 `run_native_ssh_v3.ps1 -PreflightOnly` invocation. This decision does not approve a native child. A fresh, independently checked SSH5 receipt and separate GO_PRELAUNCH are required before any native execution.

## Exact frozen inputs

- Contract: SHA-256 `1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29`.
- Input: `b6cebc1b3a44e6bd462e222690e90026e8336e1ad55f0b68b2d9212c635176b4`; the two changed source cells are PDESC and ResourceTransfer.TFTIME 7.75 to 6.
- Manifest: 66,992 bytes, schema `i03-var02-v102-prelaunch-manifest/v2`, 179 distinct source pins, SHA-256 `fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6`.
- Runner: `run_native_ssh_v3.ps1` SHA-256 `c5c117363458ffa38d61bc4296c07cdd5dc0b536953385e36a00c9e5570f5953`; validator `bb3ed0d380c86b6ded4ec857510dc5a08e30bbc8f201bed45a3767de6e770c05`; event gate `d373f07be4ea0019666cb9abb732fc4f5730bfe441bc6b5a085f97757354b10c`.
- Independent replay and self-check: `e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e` and `46b09155540c59de9369b26f4f6258d4c079e6cb75710dbd841bd075a35d73ae`. Their static-only verdicts cover the accepted parent and predicted child, 5,210 report cells each, with 58 reviewer semantic rejections. Root's exact v3 probe receipt `09fdab95afd1b53a2d728c1cfd9173f68ea24d42923a407b3e32773702985cd4` records 40 further rejections. Predicted child fixtures are not native observations.
- Root source freeze receipt: 143,694 bytes, SHA-256 `1a441e5c7ed335b7d66c0e305b00f01e6687b79e5e5090ce4196b233b1381df2`. The unique child run path was absent at this review.

## Independent static checks

The reviewer-owned audit `independent_pure_preflight_audit.py` (4,273 bytes, SHA-256 `10e6b4cea4e750ff31c38e0e30908c2119339659ee98272bcff47f0faeb5ac88`) rehashed all 179 manifest paths and six critical roles, checked 20 accepted source records, 34 accepted run records, three installed files and 139 contract source-pin checks. Its exact verdict `independent-pure-preflight-verdict.json` is 319 bytes, SHA-256 `39bfbec59966415b30800a5e9b613805eaae1db046bbaa7cb4b9370743076480`.

The runner binds the v3 independent method at both approval and postrun drift checks, uses the versioned v2 manifest, rejects a pre-existing reserved run path, and dot-sources `captured_process.ps1`. That helper launches hidden, records actual child PID, session, integer OS exit and capture error, and joins started children before returning; the runner records six ordered native/checker steps and checks versioned checker JSON before advancing. Its SSH/session/GUI/mutex and competing-runner guards are present. The historical catalog is resolved in sealed replay through a pinned owned archive and a separate live prefix/metadata rule, so a legitimate later catalog append does not invalidate the recorded native source map.

Explicit Windows PowerShell 5 parsed six production/test scripts with zero AST errors. The production preflight receipt tests returned two positives and 33 rejections; checker receipt tests returned two positives and 17 rejections. Neither test started native. The new reviewer AST audit is 670 bytes, SHA-256 `8639e6490470782722cc828242579d6942935f9d3e290c5933d16b06f0d77efc`.

The old reviewer v1 and v2 methods remain excluded NO_GO history for demonstrated event/continuation and same-time-order escapes. This decision applies only to the exact v3 method and frozen author bundle. Two failed drafts of this pure preflight audit and their original stdout/stderr are retained in `review/` before the corrected audit; they were script assumptions, not case preflight failures.

**Next gate:** run the exact frozen runner in actual SSH5 with `-PreflightOnly`, require OS exit 0, session 0 and sshd ancestry, exact protected GUI identity and response, free mutex, absent run path, `native_process_started: false`, and all 179 source-map hashes. Then issue a separate prelaunch decision bound to that receipt and the frozen method.
