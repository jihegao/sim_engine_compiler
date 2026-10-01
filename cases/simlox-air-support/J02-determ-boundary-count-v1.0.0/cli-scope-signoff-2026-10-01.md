# J02.var01 / J02.var04 CLI acceptance scope

Status: independent read-only replay GO; publication pending PR gates.

The accepted parent is `J02.var02@1.0.0` seed 01, SHA-256
`35e68a4d352d3f4e7ff62d3bd9d2c087ca2510837c33c15ad31a3dfa5d6491fa`.
The exact input matrix and source/version fingerprints are frozen in
`contract.json` and `exact-diff.json`; the installed SIMLOX executable SHA-256
is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

Five fresh session-0 SSH native runs completed import, export, calculation,
and JSON report with zero process exit errors, zero converter errors, and
native warnings #108, #126, and #211 each once. Business round-trip is
equal for every arm. Per-run author validation and the five-arm panel passed;
the five prior diagnostic probes are excluded. Every run has 11 sealed raw
files and 72 System/Stock bins, no stock demand, reconciled two-aircraft
flight hours, and all deployed aircraft ready at hour 36. GUI PID 13340
remained responsive and unchanged.

The two count-2 seeds each activated, launched, and completed two simultaneous
missions. Count zero generated none. Count four with eight aircraft completed
all four missions. Count four with six aircraft activated four, allocated all
six aircraft to missions 1–3, completed those three, and cancelled mission 4
at hour 8.33333. The report's mission success fraction was 0.75 for that arm.

An independent reviewer, without importing the author builder or validator,
replayed 5,905 checks across the five accepted runs with zero failures,
including all 55 raw SHA-256 seals. The read-only reviewer script and verdict
are in `review/`; `evidence-index.json` binds their hashes and the accepted
run IDs. The reviewer excluded all five diagnostic probes.

Publication is limited to these model parameters and fixed inputs. Other
counts, seed independence, shortage rules at other capacity/notice settings,
GUI visual content, and cross-engine behavior remain unverified. `J02.var03`
remains open.
