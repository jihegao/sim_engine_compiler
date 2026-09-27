# Resource behavior replay f8b2face

Source: sealed 4700-3 probes under
`data/local/issue18-native/f8b2face730d/v1`. Each probe completed import,
roundtrip, calculation and report export with zero conversion errors, the two
declared warnings, and all 17 non-empty business tables unchanged on
roundtrip.

The independent `validate_resources.py` replay consumes the raw multiline
ENLOG, including untimestamped availability details, plus `ResultSummary` and
half-hour `ResourceResults`. It returned the following bounded results:

| Case | Variant | Native observation | Replay |
|---|---|---|---|
| C01 | capacity-2 | request 2, grant 2, work 450--480, release 2, launch 480 | passed |
| C01 | capacity-1 | request 2 fails; no partial lease or launch; cancel 510 | passed |
| C01 | capacity-0 | request 2 fails; no lease or launch; cancel 510 | passed |
| C01 | wrong-specialty | P-CREW request fails despite P-OTHER=2; cancel 510 | passed |
| C02 | both-available | INSPECT uses P-CREW; SERVICE jointly uses P-CREW and E-GSE; launch 480 | passed |
| C02 | equipment-zero | INSPECT completes; SERVICE sees P-CREW OK/E-GSE failed and takes no partial lease; cancel 540 | passed |
| C03 | staffing-2 | two distinct owner ledgers run 450--480 in parallel; two-aircraft launch 480 | passed |
| C03 | staffing-1 | AIR-TYPE,0 runs 450--480; AIR-TYPE,1 waits then runs 480--510; launch 510 | passed |
| C03 | staffing-0 | both owners fail availability, receive no grant and do no work; cancel and stop waits at 510 | passed with cancellation boundary |

The C03 staffing-0 result does not establish a general latest-launch rule.
The fixed native profile cancelled at 510 minutes, before its 540-minute
latest-launch bound. Contract revision 1.0.2 records that observation while
leaving general cancellation semantics to C04.

These results validate the listed ENLOG/resource-report behaviors only. They
do not complete GUI publication, cross-engine equivalence, generalized
resource substitution, or C04 cancellation acceptance.
