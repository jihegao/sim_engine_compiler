# G02.var01 bounded native scope

Status: author accepted pair and independent read-only replay passed (4,780 checks, zero failures); PR gates pending.

Parent: accepted D06 two-position direct-CM input SHA-256 `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`. The separate D03 calendar-PM prerequisite is published, but PM is not exercised here. Candidate input SHA-256 `5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e` changes only ProblemDescription and adds one `FM-POS-B`/`POS-B` FailureMode and corresponding CMLocation. Source pages 250–253 and 355–370; installed manual, dictionary and executable hashes are in `contract.json` and sealed native invocations.

Accepted run IDs: `g02-var01-two-position-accepted-20261001-01` and `-02`. Both guarded session-0 SSH runs completed native import/export/calc/report, zero converter errors and 18 populated-table business roundtrips, while preserving GUI PID 13340. Each seals 12 native raw files. The two reports and event logs are byte-identical. Fixed-seed events show B-position failures at approximately 8.62763 and 20.8222, then A-position failure at 33.0996; all three missions abort and all three matching direct system CM tasks complete in 0.5 hour. Report: 72 aligned half-hour System and Stock bins, `NFAIL=3`, `NREPT=3`, 1.5 system repair hours, zero stock demand, terminal one ready.

The earlier `g02-var01-two-position-probe-20261001-01` is a source-sealed diagnostic and excluded from acceptance. The 2:1 observed event split does not validate the rate ratio. QTYPM/ENVF frequency propagation, position PM, physical replacement, invalid references, other seeds, GUI visual content, and cross-engine behavior remain unverified.
