# C09.var02 v1.0.2 ordinary arm: author read-only diagnosis

**Disposition: NO_GO_FROZEN_PAIR.** This is an author diagnosis of the sealed first-arm failure, not an independent review or a revised acceptance gate. The ordinary arm ran once under the approved SSH0 runner. Its four SIMLOX children, import/export roundtrip, converter gate, and JSON report export completed; `check_behavior` failed with `AssertionError: ('unclassified system state', 19, 2.0, 0.0, 0.9397599999999997)`. The shortage arm was never started. No native call, source edit, or raw edit was made during this diagnosis.

## Sealed evidence inspected

The run is `runs/c09-var02-v102-ordinary-ssh-20261007-01`. `closure.json` seals 13 raw files with zero SHA/size mismatches and records equal source hashes before and after execution. It records `check_behavior rejected native result`; `steps.json` shows import, export, roundtrip check, calc, and JSON report completed with exit 0, followed by a failed check_behavior exit 1. The second reserved run directory is absent.

| Original file | Bytes | SHA-256 |
|---|---:|---|
| `invocation.json` | 35,662 | `ed2e0c12f69caac6f37597cd454a71190e9260a6726d450120a62708a694d756` |
| `closure.json` | 64,946 | `30a99a36775224096dae27e938495dae5e12bb441cd493c2312baf5bef58d5df` |
| `failure-seal.json` | 4,088 | `43a64a32e56abdcf312482c16d56b391f6bb5eb0d939efa272a330e4ff86c73e` |
| `model.log` | 16,958 | `16b6e9e2ad21fc4969f2b39b2da0a7901563d1cc233ccd19d8d3c9e23f6344de` |
| `report-raw.json` | 59,521 | `301fc2529afc9f0c37288778afab0c65a3db4e82180da10c6cf9675af4b7e778` |
| `run.log` | 1,250 | `9a2701c2c444a2956caffcc5f9d4d66e080a8dd20623506a2a3e0224380bed6a` |
| `roundtrip-validation.json` | 316 | `183e31b4df80bb3770fec390459b769a6842b888e4bef83e22dd9539a21355c7` |
| `author-validation.json` | 175 | `20400b262c3715ba7f59ffad6de8b1e1b67542222c04ebcdf067bd0990197bf4` |

The root's ignored read-only freeze receipt is `../../../tmp/c09-var02-v102-run-readonly-20261007.json`, SHA-256 `f02c8cb7efee26c490e1f49b717d63fa92f426dd0020aafb6618b6542e1934b9`. It is local preservation context, not a published parent.

## Actual HOME PM sequence

The frozen input has `MaterielPM HOME-PM9` with `PMINT=9`, `PMLocation PMT=0.25` at BASE-02 using task HOME-PM, and `SubTaskResource HOME-PM/SEQ1/P-MECH/QTY1`. The model log shows:

1. At h8.71988, remote transport task 3 begins moving the one P-MECH from BASE-02 to BASE-01; it arrives at h8.96988.
2. At h9, **system PM task 3** starts on `<HOME-AIR,2>`, and **subtask 3 seqno 1 within system PM task 3** requests P-MECH at BASE-02. Availability fails. HOME ready decreases and its resourcewait increases at h9.
3. Return transport task 0 starts at h9.46988 and reaches BASE-02 at h9.96988. The same PM subtask retests, receives and books P-MECH; HOME resourcewait decreases. The log's exact active-work token is `subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing, planned to last for 0.25 hours` at h9.96988.
4. The corresponding bare `subtask 3 ... completed` token appears at h10.2199, followed by resource deallocation, system PM task completion, and HOME ready increase.

These observations show one actual HOME resource wait followed by PM work in the ordinary arm. They do not satisfy the frozen **paired** positive claim: the shortage arm is absent, and this arm's return duration of 0.5 hours equals both its TTRSS and ordinary TTRS source values.

## Why the complete-state gate failed

The frozen `report_oracle.py` at SHA-256 `623dd8c5ca6cdd83a927b55aa43b0aa85a112b52b275c96e6e722ba31a70467e` recognizes work start/completion only with a prefix matching `(?:direct repair|PM) subtask ... within system ... task` (lines 187 and 194). Native PM work uses the **bare** `subtask ... within system PM task` form. Therefore the oracle records HOME's h9–h9.96988 `NSYWR` resource wait but never opens its h9.96988–10.2199 `NSYPM` performing interval. This is an author-checker event parser defect. The separate frozen `physical()` check recognizes the bare PM token, but the report oracle does not.

In `[9.5,10)`, the oracle integrates ready `2.0`, assigned `0.0`, and resource-wait unavailable `0.93976`, omitting the final `0.06024` half-hour-bin share of PM work. Their sum is `2.93976` rather than fleet 3, triggering the exact assertion at row 19 **before** the 1,754-cell report comparison. The sealed native report has `NSYRY=2`, `NSYWR=0.9397568106651306`, `NSYPM=0.06024317443370819`, and `NSYUA=1` in that row. In `[10,10.5)`, it reports `NSYPM=0.4397568106651306` until HOME returns ready; the same missing oracle interval would affect that row too. The small decimal differences from integrations of printed event times are not the cause of this failure.

The accepted D03 calendar-PM `model.log` (8,603 bytes, SHA-256 `edd41c34046fb92e53a3f5eb8569cec3a932aa00aed8e878ecc40ef45826a4a5`) uses bare `subtask 0 ... within system PM task 0 ... starts performing` at h24 and `... completed` at h25. The accepted D12.var04 remote `remote.log` (15,136 bytes, SHA-256 `95c8b1606de5534b8ab0b41579cab54dd9f34f76a7c9431346a5c94e4a947b82`) uses the same bare form for its resource-booked CAL24 and BIG24P75 PM subtasks. The new token is consistent with those accepted PM examples; it was omitted by the frozen oracle's parser.

## Recovery boundary

Preserve the v1.0.2 contract, 256-record manifest, validator/oracle, guide, ordinary raw closure, failed author verdict, and absent second arm as the original diagnostic. A correction would require a separate versioned contract and independent review that explicitly covers bare PM subtask work edges, a read-only rehearsal against D03/D12 PM logs, full state/report cells, and fresh unique run IDs if another native pair is proposed. This receipt does not revise v1.0.2 acceptance or authorize completing its second arm, rerunning a parent, or launching another native child.
