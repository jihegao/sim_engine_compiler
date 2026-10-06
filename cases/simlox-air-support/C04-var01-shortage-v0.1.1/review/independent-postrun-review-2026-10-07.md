# C04.var01 v0.1.1 independent read-only replay

**GO_BOUNDED — 16,663/16,663 independent checks; zero failures.** The checker is standard-library only and does not import or copy an author checker. Two executions produced identical LF verdict bytes.

| Artifact | SHA-256 |
| --- | --- |
| Frozen corrected contract | `eaddbcbb400107d3c8aa1f64151a04e85303448e3997efc4b22512db6b313191` |
| Independent replay script | `337ae67b2be8f47928871b47e464f91bdc8e86513d8e3f52d9c391854534d723` |
| Independent verdict | `748bf2f4c9ba94ddf79bd5e3082cf80b2818d36245e8232691a4e3f636d89305` |
| Preserved v0.1.0 contract NO_GO memo | `4cf248f77eb0c9212c04b88778757d075ab85cd6890b364513a0545701ab9e15` |

The replay rehashed 25 accepted C04 source files against both local bytes and published Git blobs, the three selected final run chains and 33 raw SHA/size seals, direct C03 prerequisite records and 11 raw seals, and the excluded #107/#204 horizon-wait diagnostic with its four-byte SXO. All selected invocations establish SSH session 0, `sshd.exe` ancestry, the global mutex, protected GUI PID 13340/session 1/start identity and four successful ordered native stages. The reviewed accepted C04 runner tests the same GUI PID/start after each stage; the sealed step booleans were true. No native or GUI process was invoked during this replay.

All three copied source inputs and 31-table exports retain their authored row-containing tables exactly. Each has 979 scalar leaves and 201 authored row cells. Against the equal positive control, crew-zero changes only P-CREW `RQTY 1→0`. The aircraft-missing arm changes `QTYPS 2→1` **and** P-CREW `RQTY 1→2`. Relative to direct C03 staffing sources, equal and zero change only `DTIM 1→0.5`, while missing also changes QTYPS.

The physical logs support three separate outcomes. The equal arm serially uses crew ID0 for aircraft ID0 during h7.5–8 and aircraft ID1 during h8–8.5; both aircraft launch h8.5 and complete h9.5. Aircraft-missing allocates/prepares only aircraft ID0, releases its crew, cancels h8 and returns ID0 ready. Crew-zero allocates both aircraft, fails both P-CREW availability tests, books no crew, performs no preparation subtask, stops both waiters on h8 cancellation and returns both aircraft ready. Neither shortage arm launches or succeeds. The generic cancellation text has no structured reason code.

The checker parsed the sealed reports from private trailing-comma-normalized copies and compared **every one of 15,630 report cells**: 5,210 equal-arm cells against the accepted C03 report, plus 5,210 in each shortage arm against the equal baseline with only event-derived values permitted. Each arm has the declared six-table topology, 72 half-hour System/Stock/Resource bins and 11 summary fields. Changed-cell counts versus equal are exactly `0/4/158/0/218/5` for aircraft-missing and `0/4/16/0/219/5` for crew-zero, in table order. StockTotalResults is equal across arms. Resource waiting occupancy in crew-zero is kept distinct from physical work.

This is a read-only reclassification of three already accepted fixed-source CLI traces. The aircraft-missing comparison does not isolate QTYPS causality; the cancellation line does not encode a reason; and these observations do not establish a general cutoff, crew-allocation, or GUI-only rule. v0.1.0 remains excluded.
