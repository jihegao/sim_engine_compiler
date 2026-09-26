# A01 observation-window boundary probes

[Machine-readable index](observation-probes.json) holds every variant input hash, absolute immutable run path, SXI/SXO and log/report hashes, conversion result, field changes and derived event table. All runs used the same A01 source input SHA-256 `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`, one thread, one repetition, ENLOG on. The coordinator ran them sequentially through the proven SSH PowerShell context after checking SIMLOX occupancy.

| SIMPE end (h) | Import/export | Calc | Business interpretation |
| ---: | --- | --- | --- |
| 7.5, 9, 9.9999, 10, 10.0001 | Exact nonempty rows in every variant | Native error `#204`, SXO exactly 4 bytes in all five | Invalid models. No task completion or cutoff rule can be inferred. |

These first probes changed `Control.SIMPE`, `Control.RCEND` and both `ResultCollection.RCEND` rows from 36 h. Each raw `run.log` says `Some missions may not return before simulation period ends`; even 10.0001 h was rejected. The exact native input-validity margin is unknown. No JSON report or ENLOG was generated after the failed conversion. The invalid artifacts remain indexed, not silently discarded.

Two fresh positive controls with the same field changes at `SIMPE=10.5` and `12` h then passed import/export/calc/report, zero conversion errors and nonempty SXO (308,032 and 309,501 bytes). Both ENLOGs show the A01 mission launching at 8 h and completing at 10 h; `ResultSummary.RTIUP` and the last `SystemResults` interval end equal their respective SIMPE values. Thus the rejected/accepted threshold lies somewhere above 10.0001 h and no higher than 10.5 h for this input. The 20 min `DTIM` makes a latest-return check plausible, but neither the exact boundary nor a general validation formula is established. The full positive artifacts and hashes are in `simpe_margin_positive_controls` of the machine-readable index.

The second probes kept `SIMPE=36` and changed only `Control.RCEND` and both `ResultCollection.RCEND` rows. All five had four exit-0 native steps, zero conversion errors, warnings `#108` and `#126` explained for this teaching case, exact nonempty business-row roundtrip and nonempty SXI/SXO/report/ENLOG.

| Collection end (h) | `SystemResults` last end (h) | Derived mission-operation hours clipped from 8–10 h | Native `FTMO` interval integral (h) | Derived state at collection end | Native `MSTF/MSUF` |
| ---: | ---: | ---: | ---: | --- | ---: |
| 7.5 | 7.5 | 0 | 0 | planned, not launched | 0/0 |
| 9 | 9 | 1 | 1 | in flight | 1/1 |
| 9.9999 | 9.999899864196777 | 1.9999 | 1.9998998641967773 | in flight | 1/1 |
| 10 (printed tie) | 10 | 2 | 2 | complete by collection end | 1/1 |
| 10.0001 | 10.000100135803223 | 2 | 2 | complete by collection end | 1/1 |

The 9.9999/10.0001 report boundaries differ from requested decimals by about `1.36e-7` h due to native floating representation. ENLOG prints integer 8/10 h here, so the printed-tie row does not prove the scheduler's internal same-time priority. In **every** second probe, ENLOG still records notification line 7 at 7 h, launch line 18 at 8 h, success line 21 and completion line 22 at 10 h. The full simulation proceeds after early collection end. `ResultSummary.RTIUP` remains 36 h in every case, while its `MSTF/MSUF` change from 0/0 before launch to 1/1 once the mission has launched; at 9 h, the full-run completion is later than the collection end. This is an output-mapping distinction. The observed pattern suggests those summary fractions include the full-run outcome of missions that entered the collection window, but that rule is an inference from one mission, not an accepted general definition.

The first-pass local `validation.json` for the second matrix used the label `unfinished_at_requested_end_from_events=1` even when the collection end was 7.5 h, before launch. That label conflated planned/unlaunched with in-flight. Raw files and that first-pass validation are preserved. This index rederived the state read-only as `planned_unlaunched_at_collection_end`, `in_flight_at_collection_end` and `completed_by_collection_end`; [the validator](tools/validate_collection.py) and behavior tests use the corrected fields. These are derived classifications, not native output columns.

The result-collection matrix verifies clipping of `SystemResults.FTMO` for this one no-fault mission. It cannot determine native simulation-stop behavior because the SIMPE-shortened models were rejected. A01/A02's normal 36 h contracts remain complete-before-horizon cases, and the AMD128 cross-engine observation-end contract stays unverified.
