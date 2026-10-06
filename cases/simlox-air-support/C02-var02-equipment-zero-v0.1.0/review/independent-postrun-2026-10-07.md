# C02.var02 independent read-only replay

**GO_BOUNDED.** My standalone standard-library replay passed 11,252 of 11,252 checks twice, producing the same verdict bytes. It used the published C02 serial-both and serial-equipment-zero sources and their accepted final `-02` runs; it did not invoke SIMLOX or alter those files.

- The 18 published C02 source paths match local bytes except `.gitignore`, whose local CRLF eight bytes and published LF seven bytes were checked as distinct identities. The original independent C02 review, both input and closure hashes, both invocation seals, and all 22 raw SHA/size seals match.
- The only sibling input change is `ResourceAllocation` E-GSE `RQTY` 1 to 0. P-CREW stays 1, P-OTHER stays 0, both INSPECT SEQ1 requests stay one each, the INSPECT/SERVICE durations stay 10/20 minutes, and the description is equal. Both runs preserve all authored populated cells through 20 row-containing table roundtrips; native-added rows are entirely null.
- With both resources available, the log records both one-unit bookings at h7, INSPECT work through h7.16667, both releases, SERVICE through h7.5, launch h8, and success h10. With E-GSE zero, the crew test is OK but the E-GSE test fails; neither resource is booked, no work or launch occurs, and the mission cancels at h7.58333.
- Every cell of all six report tables was checked against event-derived time intervals and source settings: 5,210 cells in each arm. The zero-equipment report has aggregate resource capacity 1 and waiting one resource during the pending request; its `NRA` field is retained as a native report measure and is not interpreted as a free-worker complement. Stock ledgers are identical. Terminal aircraft readiness is one in both arms.

This establishes a single fixed-seed, source-bound resource contrast. It does not establish a general all-or-none booking rule, a cancellation formula, partial-resource behavior, GUI behavior, or a cross-engine result.

Replay script SHA-256: `09e58e95b6eb9379494c89f773dd603895a1ba188248a6d09dfb8e9ba3f62ef4`. Deterministic verdict SHA-256: `bb99a810b9caffcea8b50d313480288a725d36152d38b744fe5ce994762c41f0`.
