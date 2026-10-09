# I05.var05 scheduled item replacement — v1.0.2 candidate

Status: v1.0.1 source candidate; no v1.0.2 preflight or native run. The
v1.0.0 preflight failure is preserved under `preserved-history/`; it made no
native dispatch. Do not treat expected events as observations.

This v1.0.2 candidate derives from the accepted H02.var04 ordinary-fallback arm; the business input and contract scope are unchanged from v1.0.0. The
source already contains the `ItemReplacement` record
`TEACH-AIR-01 / TEACH-LRU-01 / BASE-01` with `SURPT=1.0` and `SURPF=1.0`.
The only planned behavioral addition is one `ChangesItemReplacement` row at
hour 5 that changes that existing record's `SURPT` to 1.5 hours. The accepted
parent input, fallback run `h02-var04-item-fallback-v100-ssh-20261002-01`,
raw event log, report, scope sign-off, and evidence index are read-only inputs
to this check and will not be rerun. The 12 original raw files currently have
Windows attributes `32` and permission mode `438`; the checker verifies each
file's bytes, hash, size, and attributes before and after reading without
changing them. The contract pins the parent run's raw artifact index, input,
event log, and report hashes.

The contract freezes the native eight-column order and metadata shape: the
four key columns carry `key: true`, while non-key columns omit the key field.
The dictionary's units and optional-field rules are recorded separately from
the native column objects. Its sole change row is
`["TEACH-AIR-01", "TEACH-LRU-01", "BASE-01", 5.0, 1.5, null, null, null]`;
`TIMEC` and `SURPT` are doubles in hours, and optional `SURPF`, `SURPD`, and
`NOTE` are explicitly null. The source gate allows only a `ProblemDescription`
update and this one table appended after the parent's final table. It requires
every other parent table, typed cell, and the original `ItemReplacement` row
to remain unchanged.

The installed SIMLOX 2017 manual pages 504–505 and table dictionary define the
scheduled key as `MID`, `IID`, `STID`, and `TIMEC`; `MID` names the mother
system/item and `IID` the child item. They limit changes to an existing
`ItemReplacement` object and state that a started, unfinished activity does not
change retroactively. The parent has one named mother-system/child-item row at
one station, so this contract does not cover group precedence, multiple
relations, or an in-progress activity.

The accepted H02.var04 fallback run starts three 1-hour ordinary replacement
activities after fixed-seed primary-LRU damage. The prospective check is that
there is no replacement activity at hour 5 and that a replacement activity
started afterward uses the new 1.5-hour duration. Subsequent damage timing,
readiness, stock transactions, and report bins must be read from the sealed
child evidence; this contract does not assume a general shift of stochastic
times.

The [contract](contract.json) contains the frozen parent fingerprint, exact
change row and schema, typed values, allowed parent-to-child diff, units,
manual rules, expected timeline, acceptance gates, and limits. Independent
contract and source-delta reviews approved the source scope. [source-freeze.json](source-freeze.json)
pins the candidate input, builder, source checker, contract, README, accepted
parent evidence, and reviewer record. The package remains not preflighted and
has no native child run; fresh run-owner, GUI, session, mutex, source-pin, and
prelaunch gates still apply before SSH or native execution.
