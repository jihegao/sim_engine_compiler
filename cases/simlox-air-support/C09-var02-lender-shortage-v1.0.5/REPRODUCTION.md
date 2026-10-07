# C09.var02 v1.0.5 child-only reproduction

**Status at this snapshot: prelaunch; no v1.0.5 native run or publication.** The frozen [contract](contract.json) and [prelaunch manifest](prelaunch-manifest.json) define one prospective child. The central `../publication-index-v1.json` is authoritative for any later publication state. The frozen `README.md` is a contract-stage snapshot; this guide can record later run and review receipts without altering that snapshot.

## Original evidence and static checks

The child starts from the exact v1.0.2 ordinary input (`b971efb4…`) and changes only ResourceRemoteSupport.TTRSS 0.5→0.125 and ProblemDescription.PDESC. It does **not** rerun the ordinary arm. The published bounded ordinary control is `../C09-var02-lender-shortage-control-v0.1.1`; its [evidence index](../C09-var02-lender-shortage-control-v0.1.1/evidence-index.json) pins 101 source files, 130 original raw files, and 77 separate accepted local/Git identities. Its [raw custody map](../C09-var02-lender-shortage-control-v0.1.1/raw-custody-map.json) lists the nine accepted dependency runs (117 raw files plus nine closures and invocations) and the sole failed v1.0.2 ordinary run (13 raw files, closure, invocation and failure seal). The separate C03 source and run are at the external original path named there. Restore any missing original byte-for-byte at its declared path, then verify SHA-256 and size; a fresh calculation is not a substitute.

The historical root publication index has separate identities: the local CRLF snapshot is preserved as [publication-index-at-base.json](preserved-root-context/publication-index-at-base.json), 483,289 bytes/SHA-256 `8e403bf64ffc068a5ccd6092214da2ccd9626205c33d8722b6dd348a1af36ad1`, while base Git `d1d9a4d…` holds 482,723 LF bytes/SHA-256 `e8d50785f23c2458b86395bd782c109c691dc8aa132ae977fe374702c6411f17`. The parsed 486 entries agree. The four small root selection/owner/publication receipts are copied byte-exact into `preserved-root-context/` and retain their original contract pins. Live preflight requires the root catalog's original bytes; sealed replay uses the archived snapshot after an authorized catalog append.

From the package directory, run the bundled Python checks without `--write`:

```powershell
Set-Location 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.5'
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 .\build.py
& $py -X utf8 .\verify_sources.py
& $py -X utf8 .\self_check.py
& $py -X utf8 .\make_prelaunch_manifest.py
```

Expected identities: child input 47,164 bytes/SHA-256 `a036c16bbdd28b35047ba8a064722c6a1bde21c036435263dd5713dd710767a4`; exact two-cell diff SHA-256 `3feb14a7e88ff6d36360d5f9623c79f3519e1bf18413d145024d26dac17edddd`; manifest 132,674 bytes/SHA-256 `f16251fc6eff445a48a30fc7632c85a0dc609639f8f7212980c393b88a1dbbed`, 384 source records. The source verifier reports 30 direct contract pins, 101 published source disk/Git pairs, 77 distinct accepted local/Git references, 130 raw seals and ten closure/invocation pairs. The self-check reports 1,754 accepted control report cells, 1,754 synthetic shortened-return oracle cells and 24 semantic mutation rejections. The synthetic fixture tests code paths; it is **not** native evidence.

## Protected native boundary

Only the root controller may invoke the runner. Independent exact-file review must first approve this manifest and runner. The controller then uses an actual SSH session 0, PowerShell 5 file invocation with stdin closed to run pure `-PreflightOnly`:

```powershell
ssh -n -o BatchMode=yes user@127.0.0.1 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.5\run_native_ssh.ps1 -PreflightOnly'
```

That must create a unique `review/preflight-ssh0-*.json` with zero native children, absent run path, exact source hashes, SSH0/sshd ancestry, free mutex and the sole responsive protected GUI PID 13340/session 1/start 1790590196826. A **fresh** `review/independent-prelaunch-go.json` must bind the actual preflight SHA, manifest, contract, child input, runner, validator, final independent replay method SHA and reserved run ID. A v1.0.2 approval does not apply. Only then may the controller invoke the same file without `-PreflightOnly` once:

```powershell
ssh -n -o BatchMode=yes user@127.0.0.1 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.5\run_native_ssh.ps1'
```

The sole reserved directory is `runs/c09-var02-v105-shortage-ssh-20261007-01`. The runner waits for each hidden native child and never terminates or retries it. It records actual child PID/session, checks GUI identity before/after each step, preserves Python checker stdout **and stderr**, and seals available raw/source/failure evidence even when a gate rejects behavior. No other run ID or accepted parent is launched.

## Postrun read-only replay and diagnosis

After a sealed run exists, use `& $py -X utf8 .\verify_sources.py --sealed-replay`, `& $py -X utf8 .\check_roundtrip.py .\runs\c09-var02-v105-shortage-ssh-20261007-01 shortage`, and `& $py -X utf8 .\validate_native_cli.py .\runs\c09-var02-v105-shortage-ssh-20261007-01 shortage`. These commands print results without overwriting a sealed raw file. The independent `review/independent_replay.py` is a separate method and must pass on its own. Compare the actual `closure.json` and every raw SHA/size with the frozen records; the candidate input, import/export, converter diagnostics, four native stages, two Python check stages, SSH0/mutex/GUI identity, physical typed loan/return and PM edges, and all **1,754 cells across six report tables** are gated. Exact IDs, nulls, source counts and whole-bin values have zero slack. Fractional event-derived fields use the frozen per-field half-printed-unit propagation and ceilings; only the two predeclared HOME h9 wait cells can use the conditional ≤3×10⁻⁶ representation allowance.

If a pin fails, restore original bytes at the declared path and check local/Git identities separately. For an import/export or diagnostic failure, inspect `import.log`, `export.log`, `roundtrip-raw.json`, `roundtrip-validation.json` and `run.log`; do not revise the frozen diagnostic gate. For a physical or report failure, inspect `model.log`, `report-raw.json`, `author-validation.json`, `check_behavior-stderr.txt`, `steps.json`, `closure.json` and `failure-seal.json` if present. Bind transport start/arrival by task ID and station/quantity, HOME failed P-MECH request to that same absence span, and PM work to the observed regrant. A source/event mismatch or unexplained report cell is a sealed NO_GO for this version. Any altered source, numeric rule, guard, or native retry requires a new version, new unique run ID and independent review.

The v1.0.3 and v1.0.4 [excluded contracts](../C09-var02-lender-shortage-v1.0.3/contract.json) and [v1.0.3 NO_GO](../C09-var02-lender-shortage-v1.0.3/review/independent-contract-no-go-2026-10-07.md), [v1.0.4 NO_GO](../C09-var02-lender-shortage-v1.0.4/review/independent-contract-no-go-2026-10-07.md) remain unchanged. The v1.0.2 original prospective pair failed and its shortage arm was not started; this child does not retroactively accept that pair. Any result remains limited to one seed, one 12-hour three-system CLI topology and the observed source-bound return cycle. It does not establish a general lending priority, persistent mechanic person identity, GUI visual result, cross-engine equivalence, or performance.
