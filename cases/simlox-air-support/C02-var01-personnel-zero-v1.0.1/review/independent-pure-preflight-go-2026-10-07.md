# Independent pure-preflight review — C02.var01 v1.0.1

**Decision: GO_PURE_PREFLIGHT only.** The controller may invoke the exact frozen runner through actual SSH PowerShell 5 with `-PreflightOnly`. This decision does not approve a native SIMLOX child. A separate review must bind the resulting receipt and current GUI, mutex, source map, and absent run before a native launch.

## Exact reviewed bytes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `contract.json` | 48,041 | `e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12` |
| `native-input.json` | 42,962 | `bab34055ae4f2ee3efac4fa9cb8f545ba2355daad0751a7d5508947f17d3cec2` |
| `prelaunch-manifest.json` | 52,079 | `c1c2665b9e8c8a7e054c47395a91110e0f4852605573ca49bc6aa69b2308e6e2` |
| `run_native_ssh.ps1` | 14,223 | `175656baa5cadd49a9b9db85862bcfa5c933c205a8514c4c8f996c164f300d94` |
| `validate_native_cli.py` | 8,796 | `297ea19ad38d866d410c0c009624602d7fa2789506ead9b25c93ea500f6c9742` |
| `review/independent_replay.py` | 40,642 | `f3513bd42042597a49b6bf276117dc3a458d48ab079b4297b14a3be9aa19578f` |

The manifest contains 155 distinct source keys. I rehashed every listed local file against its byte count and SHA-256: 155/155 match. A deterministic read-only regeneration produced the same manifest hash. The provisional 50,584-byte manifest and earlier runner/test drafts remain separately pinned under `preserved-prefreeze/`; they grant no launch authority.

## Static and read-only results

- Source builder: exactly ProblemDescription.PDESC and P-CREW ResourceAllocation.RQTY 1→0 among 236 flattened cells; no other table, instance, column, or cell differs.
- Source verifier: 47 accepted published source identities, 55 accepted raw seals, and 12 context pins pass. Accepted C02/C01 local CRLF and published Git LF identities remain distinct. The independent replay separately checks those 47 local/Git blobs against the exact base commit.
- Author static check: the sealed control reconciles all 5,210 native report cells; the crew-zero role-swapped synthetic fixture reconciles 5,210 cells across 21 direct checks and mutation probes. This fixture is parser and numeric coverage, not a native child result.
- Independent replay: control 5,210 cells / 5,956 checks; synthetic crew-zero 5,210 cells / 5,976 checks including 15 semantic rejections. The child path remains fail closed while its run directory is absent. It uses source/event-derived expectations, exact zero/discrete/null/identity checks, printed-token bounds only for supported fractional cells, and rejects a tiny whole-bin residue at a synthetic printed `7.50000` boundary.
- Actual local Windows PowerShell 5 parsed all six package `.ps1` files with zero syntax errors. The production preflight receipt test had two positives and 33 rejections; the checker JSON receipt test had two positives and 15 rejections. Both local tests reported `native_process_started=false`.
- The runner requires SSH PowerShell 5 session 0 with sshd ancestry, a free host mutex, one protected responding GUI PID 13340/session 1/start 1790590196826, active WTS GUI session, no competing runner/native child, and an absent unique run path. It sets its owned-run flag only after creating that absent directory; a pre-existing run cannot receive its failure seal. Six steps record actual PID, session, integer OS exit, streams, and GUI preservation before the success predicate. Checker stdout is parsed against versioned JSON, input/export SHA, and 10,420 parent-plus-child report-cell count. Closure seals all run raw bytes and before/after source maps; failure evidence remains preserved.

The exact reserved run `c02-var01-v101-personnel0-ssh-20261007-01` is absent. There is no independent prelaunch approval or case SSH preflight receipt yet. The next gate is one actual SSH `-PreflightOnly` invocation; its byte-sealed receipt requires a fresh independent `GO_PRELAUNCH` decision.
