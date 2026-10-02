# I02.var14 bounded CLI signoff — double-`<OUTSIDE>` counterexample

**Decision:** Restricted GO for the observed installed-CLI response; NO-GO
for the planned native rejection expectation. The input remains prohibited
by the installed manual, and this signoff does not endorse it for modeling.

## Source and frozen delta

Accepted I02.var01 IN source SHA-256 is
`85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d`.
The v1.0.1 child input SHA-256 is
`de0e6c5acb053c48528598d91b541603f78cfdac68f866899c2240740e58ced5`;
exact diff SHA-256 is
`fefdb10df77e84c4aa89cccba2b2a732aa0980e189a002b7e8a9a8df2b7041f3`.
Only row 0 `ItemTransfer.STTID` changes `DEPOT-01`→`<OUTSIDE>`, alongside
the provenance description. The other 30 tables are identical to the
accepted parent. The installed manual PDF SHA-256
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`
states on printed p476 that both endpoints may not be `<OUTSIDE>`.
Installed executable SHA-256 is
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

## Native observation and ledger

The fresh `i02-var14-both-outside-v101-ssh-20261002-01` session-0 SSH run
preserved GUI PID 13340 and completed import, export, calculation, JSON
report and exact 22-populated-table roundtrip with exit code zero. The
converter reported `Errors: 0, Warnings: 1` (#108 for logging) and emitted
a nonempty SXO. The double-`<OUTSIDE>` row survives the roundtrip, but the
model log has no scheduled transfer task or h4 event. The sealed-SXO depot
item report `i02-var14-depot-item-v101-ssh-20261002-01` has 72 half-hour
bins. Two closures seal 14 local raw files.

| Observation | Accepted I02.var01 IN | I02.var14 child |
| --- | --- | --- |
| h4 scheduled task | One IN arrives with physical ID 1 | No transfer event |
| Depot `STSZ/STOHA` at h4 | 2/2 | 1/1 |
| Depot `STSZ/STOHA` at h10 | 2/1 after ordinary ID0 issue | 1/0 after same issue |
| Depot terminal `STSZ/STOHA` | 2/2 | 1/1 |

The depot nominal and on-hand series match before h4. They differ by one
in each of the 64 bins from h4 to h36; other `ItemResults` fields match.
`ItemResultsTotal` differs as a horizon average, not as a terminal
measurement. Selected mission, system, aggregate stock and summary tables
and all default business report tables are equal to the parent, apart from
the description and item-position tables. Both terminal aircraft are ready.
Physical item identifiers after h4 differ because the parent has the extra
IN item; mission and aggregate equality does not imply byte-identical logs.

Author replay passed 24/24; independent read-only replay passed 511/511,
including the accepted parent and child raw seals. The earlier local
v1.0.0 rejection-hypothesis probe, closure SHA-256
`2b1526c8b16aae6825457ec7bcea6011c631af4ba515e8c29c80b5c949f0f8e0`,
was stopped by its expected-rejection gate when conversion unexpectedly
succeeded; it is not counted as an accepted run. `evidence-index.json`
identifies the accepted and excluded local raw evidence.

## Limits

One h4 one-unit row, one IID/depot/seed and the pinned CLI build are tested.
Other double-`<OUTSIDE>` rows, error precedence, general silent handling,
GUI visual behavior and cross-engine parity remain unverified. I02 and
Issue #18 remain open.
