# I02.var13 bounded CLI signoff — terminal transit and transfer backorder

**Decision:** Native behavior accepted for the two fixed endpoint examples
below, with source-bound independent replay. This is not an acceptance
of general transfer-horizon semantics.

## Parent and source

The transit child derives from accepted I02.var04 positive BETWEEN duration,
source SHA-256 `607b5d5bc9d3c850b533b4bc50e202e6719c23182b47038fdf056222bfce2f39`.
The backorder child derives from accepted I02.var05 zero-source BETWEEN,
source SHA-256 `00cebb18be952522b1bbfd1885edc40f2c9b4da148d000cf5326309360cc6453`.
Child sources are respectively `1ab184c30a5ff06b28bfa8b84dda423b639b51140b22a549cee09f05fb3a32d9`
and `020faa03b794fc5a57a8c3ccd931731370316a925c52d1ef85ca5ee2042c2c64`;
exact-diff SHA-256 is `f7347b61df6da56ba2ed300737c1b9e9945d759b1eabd7cc39db0016332c935d`.
Each child changes only Control, ResultCollection, OperationProfile, and
ProblemDescription; 28 other tables including ItemTransfer and stock are
identical to their parent. The h8/h20/h32 mission rows become one referenced
h0 `IQTY=0` row, following the accepted D02.var05 zero-initiation syntax.
The installed SIMLOX executable SHA-256 is
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

## Native observations

The session-0 SSH runs `i02-var13-transit-v100-ssh-20261002-01` and
`i02-var13-backorder-v100-ssh-20261002-01` completed import, export,
calculate, report and exact authored-table roundtrip with exit code zero,
zero conversion errors, and GUI PID 13340 preserved. Each has 22 populated
authored tables. Four sealed-SXO station reports contain 14 half-hour bins
for h0–7 and six bins for h0–3 respectively. Six closures seal 32 raw files.

| Arm | Direct physical event | Final station ItemResults | Ledger |
| --- | --- | --- | --- |
| Transit, h7 | IN ID1 at h4; BETWEEN takes ID0 at h6, `TFDT=2`; no h8 receipt within horizon | DEPOT-01 `STSZ/STOHA=1/1`; BASE-01 `0/0`; ordinary `NBO=0` | Initial depot1 + IN1 = terminal depot1 + in-transit ID0 1 |
| Backorder, h3 | h2 BETWEEN task starts/arrives with zero; transfer backorder 1 added; no h4 IN within horizon | DEPOT-01 `0/0`; BASE-01 `STSZ/STOHA=1/0`; ordinary `NBO=0` | No physical item exists or moves; nominal target position rises before fulfillment; transfer backorder is log-visible |

The native model logs end at the configured endpoint. A transfer backorder
remains unremoved in the h3 log; no terminal transfer-backorder counter is
asserted from `ItemResults.NBO`, which is zero. No mission initiates, and the
aircraft remains ready. Author replay passed 48/48 checks. Independent
read-only replay passed 420/420, including 32 raw seals and a check that
aggregate `StockTotalResults.NBO` also remains zero despite the log-visible
transfer backorder. The separate review verdict and exact raw fingerprints are in `review/` and
`evidence-index.json`.

## Limits

One IID, two stations, seed 1, zero mission initiation and two endpoint
times were tested. The two arms have different accepted parents and are not
a one-factor head-to-head comparison. Active-demand priority, arbitrary
durations, GUI visual behavior and cross-engine parity remain unverified.
I02 and Issue #18 remain open.
