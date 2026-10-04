# F03.var04 independent static preflight — 2026-10-04

**GO for two serial guarded diagnostic native runs.** The independent reviewer checked the frozen F03.var03 parent input, closure and signoff; accepted E08 lateral donor input and signoff; child source hashes, input tables, contract, runner and roundtrip checker before native execution. This was a read-only preflight, not a semantic verdict.

The parent has 32 tables. Both children add the exact donor five-column LateralSupport table, place BASE-01 and BASE-02 in LAT-01, and give BASE-02 one opening LRU. The pair changes only descriptive PDESC and Control.ENLAT Y/N. Depot routes, missions, repair, PM, resources, seed and other business tables remain fixed. The donor's lateral rule is IMMEDIATE with TLAT 0.5 hour and DLAYL N.

Python and PowerShell parsed without errors. The runner pins contract, diff, sources and accepted ancestry; requires session-0 SSH with sshd ancestor, the host-wide native mutex and unchanged active GUI PID 13340; and checks the four hidden native steps, warning #108 as the sole converter diagnostic, exact authored-table roundtrip and raw closure. The accepted parent and donor use the same diagnostic gate.

The reviewer conditioned any positive lateral claim on matched BASE-01 demand and a physical peer item issue. The authored configuration alone does not prove lateral transport or later path parity.
