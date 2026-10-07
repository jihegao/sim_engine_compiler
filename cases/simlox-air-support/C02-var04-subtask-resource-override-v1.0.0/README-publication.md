# C02.var04 publication guide

The original [README.md](README.md) is a frozen prelaunch source snapshot. Its statement that no native result was accepted yet records the state at that freeze; it is not the current result.

The approved joint and crew-only native arms completed once. The [results](results-2026-10-07.md) and [scope signoff](cli-scope-signoff-2026-10-07.md) describe the bounded outcome: the explicit joint subtask could not obtain E-GSE, while the explicit crew-only subtask performed from h7 to h7.5, followed by a successful h8–10 mission. Author replay passed 5,688/5,688 and 5,692/5,692 checks; independent replay passed 11,405/11,405 and covered all 10,420 report cells. The [evidence index](evidence-index.json) seals the source and local raw identities.

The first staged publication attempt was rejected because the new root publication-index entry used paths relative to the repository root. The rejected package index, builder and signoff bytes are preserved under `review/excluded-staged-*`; the [diagnostic](review/excluded-staged-publication-diagnostic.json) pins the rejected root snapshots and independent NO_GO memo. The repair changes publication documentation and index wiring only. No frozen prelaunch source or native raw run was changed or rerun.

This is fixed-seed, one-aircraft, one-INSPECT-subtask native CLI evidence. Publication in the shared index and merge remain separate gates; it does not establish a general resource override, GUI behavior or cross-engine parity.
