# Independent v1 method: NO_GO_METHOD

The frozen independent method cannot authorize a native run or publication. It checks allowed log text and some aggregate counts, but three in-memory mutations to its predicted child log pass its `child_physical` gate:

1. All four `no failures` / `no PMTasks` continuation pairs move away from their `System arrives` owners to the terminal log region.
2. An additional `Free resources at: <BASE-01,0> P-CREW 2` snapshot appears while one crew is booked and only one is local.
3. An extra typed `nbr ready increased at unit` event appears at h8 during preparation.

These contradict the contract's event ownership and complete physical ledger. The probe uses synthetic in-memory text only; it does not alter accepted raw files or make a native call. The v1 STATIC_ONLY outcomes remain historical tests, not GO_PRELAUNCH.

Frozen v1 identities (bytes, SHA-256):

- `independent_replay.py`: 43,499, `5ad26b738d0b3fc36daa494b6dfbab77c5188cb0248d0e81f365e67b7f27addc`
- `independent_self_check.py`: 11,956, `4dc362332cfe150f1e61f23ad08552231cc98d9e1805cd625f80df773b2b35ce`
- `independent-static-verdict.json`: 166, `e8a148bbbceed18338de09d1668bb68d0a375a57faec242172ab4c31757ebd5d`
- `independent-self-check-verdict.json`: 993, `7bf2ba26b8c062659d3f6138891882b2867f24d894bfa7a90c4a254ffe4ec88e`
- Root probe `tmp/probe-i03-var02-independent-ledger-20261007.py`: 1,756, `ed2ec5eb8371d90c8bf24b3f1b11cb2801ccd1ceef330978008e1a2a4d6b045b`
- Root receipt `tmp/i03-var02-independent-ledger-probes-20261007.json`: 555, `078ddc254f135c2df1041128e758439effbc10604ec29f8bb91d605c6d906678`

Recovery requires a separate v2 method and self-check. It must bind continuations to the immediately preceding typed event and owner, reconcile free/booked/outside and ready-pool state after every edge, and reject orphan, duplicate, misplaced, or contradictory diagnostics. The existing v1 files and their pins must remain unchanged. Any manifest that pins v1 as the independent approval method is unapproved.
