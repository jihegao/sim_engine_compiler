# Independent pure-preflight review — C09.var02 v1.0.2

Decision: **GO_PURE_PREFLIGHT only**. The frozen files support one read-only, actual SSH0 PowerShell 5 `-File ... -PreflightOnly` invocation. This decision does not approve a native SIMLOX process or either reserved run. A separate exact-receipt GO_PRELAUNCH is required.

## Exact frozen bytes

| File | SHA-256 | Bytes |
| --- | --- | ---: |
| `contract.json` | `5433d55e26e06ededeb0fb3f714548ea98192b012f6de41ebb795930b624f236` | 82021 |
| `prelaunch-manifest.json` | `0789c128a656b0d405932ec053dc80853ecc8f7dd692f9b4eb3041e80ee8ce4a` | 87539 |
| `run_native_ssh.ps1` | `e70a22a81acf0b9da1ee76dd2dbd5e6fc93f029cb26fe9630696f345e7eca7a7` | 15083 |
| `validate_native_cli.py` | `550730bef8cce37fadd48583ea6f560aaee6e91abc7c2d89c705877b985b42be` | 14961 |
| `report_oracle.py` | `623dd8c5ca6cdd83a927b55aa43b0aa85a112b52b275c96e6e722ba31a70467e` | 22824 |
| `self_check.py` | `670ebe94e8826d64f9264fc5a8ae412f504e7677df606b66b2c92d0829846899` | 12723 |
| `verify_sources.py` | `196cbb959d8f6943eb02ad8939ad7a2a18a9aa3909330a557ffb3684176472c6` | 4548 |
| `review/independent-contract-go-2026-10-07.md` | `3f89588e7be261480e1a7ea8cc6b2127fc8e84c2c0cd043651433b7078a55a95` | 3666 |

I independently rehashed all 256 unique manifest source records against disk after the static tests: zero SHA or size mismatches. This includes 78 accepted local/published source pairs, 117 accepted raw files, nine closures and nine invocations, installed tools, and 23 excluded v1.0.0/v1.0.1 pins. Both v1.0.2 run directories were absent. No accepted raw or excluded source was changed.

## Static behavior and safety gates

- My separate source gate parsed both frozen inputs as full 32-table authored sources, checked the 78 local/Git source identities, 117 raw seals, nine closure/invocation chains and 23 exclusions, and rejected five positional/source mutations. The author verifier also passed those pins. The exact source changes and unchanged horizon, resource, system, PM and stock settings match the corrected contract.
- The author self-check reproduced all 5,210 cells of the accepted C09 remote control and rejected 24 adversarial mutations. I separately checked the report topology and per-RID/station resource-edge parsers against accepted raw data, including metadata-shape, overlapping mechanic booking, wrong-station booking, and late-receipt mutations. These are static controls, not a child outcome.
- The corrected oracle treats complete-bin integer/count values exactly. Its h8 `NSYMO` probes reject `0→0.00001` and `2→2.00001`; an interior source-derived `FTMO=2/3` gets only numeric serialization tolerance. Printed-time-derived fractional exposures use their declared field-specific bounds. It checks separate resource requests, borrowing/return transport cycles with IDs, HOME PM task linkage, per-station capacity, zero booking in transit, and all six expected report tables. The sealed mode checks the raw closure and source-before/after map; live mode checks the available five completed stages while `check_behavior` is active.
- PowerShell 5 parsed the runner with zero AST errors. The runner binds exact source hashes, SSH0/sshd ancestry, a free global mutex, protected GUI PID 13340/session 1/start 1790590196826/responding, absent run IDs, serial stage order, child session 0, converter context, and failure sealing without terminating the protected GUI. JSON/log reads in PowerShell specify UTF-8. Python is invoked as a file without `-X utf8`; the actual SSH5 preflight must establish that the frozen invocation works on this host.

The earlier v1.0.1 frozen bundle remains **NO_GO_STATIC** because its blanket boundary tolerance admitted incorrect exact h8 counts. This v1.0.2 decision applies only to the SHA values above. The next gate is a clean actual SSH0 PowerShell 5 `-PreflightOnly` exit with a pinned receipt showing the same manifest, run absence, mutex/GUI state, and `native_process_started=false`. Only then can an independent GO_PRELAUNCH bind that receipt and approve the single guarded native pair.
