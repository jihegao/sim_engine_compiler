# CLI scope signoff — C05.var03 counterexample

Decision: **GO_BOUNDED_READONLY_COUNTEREXAMPLE** for one sealed crew-arm trace; **NO_GO_FROZEN_PAIR** for the original v1.0.2 positive two-arm contract. The radio arm was not run.

The frozen crew run has six ordered steps; import, export, roundtrip, calculation and report completed, while the original behavior validator failed. Its 13 raw files and failure seal are preserved. Source before and after matches the 77-pin prelaunch manifest; the accepted lineage contains 23 local/published source identities and 48 accepted raw seals. Native conversion reported zero errors, four attributed warnings, and zero notes. The authored 24 row-containing tables roundtrip exactly, with only all-null placeholders in otherwise empty tables.

At h7, two transient MISSION-CREW unit bookings are released during configuration. At h8, configured A0/B1 launch with crew quantity zero and succeed at h10. There is no radio-arm observation. The retrospective author checker reconciles all 5,210 report cells and passes 6,023/6,023; the independent replay separately reconciles all 5,210 cells and rejects eight tamper probes.

This is a source-bound CLI observation, not a positive result for the failed pair or a general behavior guarantee. It does not prove serial item-to-aircraft continuity, a universal resource inheritance rule, or GUI behavior. This author signoff is a snapshot of the evidence gate; consult the repository's `../publication-index-v1.json` for current publication status.
