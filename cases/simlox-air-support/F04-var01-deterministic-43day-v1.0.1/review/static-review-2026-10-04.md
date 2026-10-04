# F04.var01 v1.0.1 independent static preflight — 2026-10-04

**GO for two fresh serial guarded native runs.** The independent reviewer checked the accepted F03.var01 staffed parent input, closure and signoff; accepted J04–J08 signoff pins; the corrected source, exact diff, contract, runner and roundtrip checker. This was a read-only preflight, not a native outcome verdict.

The child differs from its parent in exactly 14 cells across seven tables: description; Control simulation/result ends; System and two Item failure rates; two deployment quantities; two OperationProfile quantities and two periods; and both ResultCollection ends. BASE-01 has five aircraft, BASE-02 three, each failure rate and MissionType.MFF is zero, the horizon is 1032 hours, and both schedule roots use IQTY21/IPER1008. The excluded v1.0.0 native logs showed IQTY21/IPER48 compressed requests to 48/21 hours; v1.0.1 targets 1008/21 = 48-hour spacing. The last planned BASE-01 RISK/BASIC requests are h981.5/h984.75; BASE-02's last is h968.

The accepted G12 zero-FRT precedent requires converter warning #2053 for each of the two Items. The v1.0.1 contract and runner require exactly Errors0, Warnings3 ordered #108/#2053/#2053 with the named LRU/SRU rows, Notes0. Python and PowerShell parse without errors. The runner pins source and prerequisite hashes and requires session-0 SSH, sshd ancestry, host-wide mutex, active GUI PID13340, hidden CLI steps, exact authored-table roundtrip and raw closure.

Native 48-hour spacing, no failures, PM/resource ledgers, report metrics and terminal state remained post-run gates.
