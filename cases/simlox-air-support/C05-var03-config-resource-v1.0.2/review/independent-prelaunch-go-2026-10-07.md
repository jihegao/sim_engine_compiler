# Independent prelaunch review: GO_PRELAUNCH

Decision: **GO_PRELAUNCH** for one serial, guarded native pair using only the two reserved C05.var03 v1.0.2 run IDs. This decision binds the exact frozen bytes and actual SSH PowerShell 5.1 preflight below. It does not classify the native outcome; each arm still must pass its frozen converter, roundtrip, physical event, stock, resource, and full report gates.

## Frozen source and actual host preflight

- Contract `b397b217fbf19ec9b6ae9a166a7b3124144f7ec74680675b1fc47b3b69469d0f`.
- Manifest `00a35aa5715856a8819cd5899fb1a1f05ec83fd15539368bbabcca7a539fbd1b`, 77/77 exact size and SHA-256 source pins.
- Runner `65d048f21dfb27982090bba56879a1b77c7c3366a2dd42338275fd34c12a33ca`; validator `7fb6706ec19de0b9978a91452a22b0a6c7e67eac8ed9742e7afdbbdea4bbf5ad`.
- Inputs: crew `6c88e8f5b078e7d02184d8612acda6b5d20ed94398943a7ca7f3472830c2f7ae`; radio `235a6ce2850fb12dc5d3f4da67e709e8646fa2f4f6e2aa9cee3e106da335f57a`.
- Actual `ssh -n` PowerShell 5.1 `-File ... -PreflightOnly` exited 0. Its saved 10,797-byte output is `review/preflight-ssh0-20261007T012658707Z.json`, SHA `5e664c7fafb3ae17f8ae03ce39037ad53e8677859c0d2415237e7e9dee9fb259`.
- The separate root invocation record `review/root-ssh-preflight-invocation-20261007.json`, SHA `adb7b6ffa64f4c7f9942329cd58cee165ffcf006a835d11f2645a63e482a07e9`, binds the exact `ssh -n` command, exit 0, 3.596208-second duration, complete tool output, saved preflight hash, and absence of a native process or run directory.

I independently parsed that saved output and checked its schema, exact two run IDs, manifest hash and all 77 reported source hashes against the still unchanged files. It reports SSH session 0 with `sshd.exe` ancestry, the host mutex free, the protected GUI PID 13340/session 1/start 1790590196826 responding, 48 accepted raw seals, both run directories absent, and `native_process_started=false`. I checked that the package had no `runs` directory and no preexisting approval file before writing this approval. The source verifier also passed 23 accepted local/published Git identities, 48 raw seals, all 70 old v1.0.1 manifest entries and the pinned failed SSH5 encoding probe. PowerShell syntax had zero errors; explicit UTF-8 reads address the v1.0.1 no-go failure. Independent PREP_ONLY replay controls and 11 tamper probes passed, as did the author's 40/40 static self-check.

The companion `review/independent-prelaunch-go.json` binds the runner-required decision, manifest, runner, validator, contract, both inputs, both run IDs, and the exact actual SSH preflight path/hash. The runner must revalidate all these and the protected host state at native launch. Execute at most this one approved pair, preserve its original raw bytes and any failure seal, then require independent postrun replay before acceptance or publication. No v1.0.0 or v1.0.1 diagnostic is converted into an accepted native result by this decision.
