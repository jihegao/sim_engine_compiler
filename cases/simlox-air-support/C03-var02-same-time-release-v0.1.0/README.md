# C03.var02 — same-time crew release and subsequent work

This is a **read-only reclassification** of the accepted C03 1.0.2 one-crew and two-crew final CLI runs. It adds no native run or model input. The [contract](contract.json) pins the accepted C03 source and closures, all 22 raw seals, and the published C03.var01 staffing result that uses the same runs.

In the one-crew log, aircraft 0 finishes its preparation subtask at h8, frees P-CREW, and the station lists aircraft 1's waiting subtask. Aircraft 1 then passes a same-time availability retest, receives and books the same P-CREW, and starts its half-hour work at h8. Its work ends h8.5; the two-aircraft mission then launches and succeeds h9.5. In the two-crew control, both aircraft prepare concurrently h7.5–8 and the mission launches h8, succeeding h9.

The [author replay](check_reclassification.py) passed **16,582/16,582** checks twice with identical verdict bytes. It recomputes the accepted source's local and Git byte identities, both input/closure/invocation chains, all 22 raw SHA/size seals, exact authored roundtrips, the physical h8 line order, and every cell of six report tables (**5,210 per arm**). The reports match in description, summary, and stock; the observed pair differs in 12 System, 219 Resource interval, and 4 Resource total cells.

This h8 sequence is a source-bound observation and overlaps the accepted C03.var01 staffing evidence. It does not establish a general same-time scheduling or crew fairness rule. The [scope note](cli-scope-signoff-2026-10-07.md) records the limits. A separate [independent replay](review/independent-postrun-review-2026-10-07.md) passed 11,732/11,732 checks. The evidence index pins the final source and raw bytes; independent publication review remains required.
