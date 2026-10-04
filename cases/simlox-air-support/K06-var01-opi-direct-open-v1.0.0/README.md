# K06.var01 — common-format `.opi` direct open

This bounded probe copies the accepted K02.var01 native `model.sxi` byte-for-byte to an immutable local `model.opi`. The model, seed, mission, stations and all business parameters are unchanged. SIMLOX 2017 opens the `.opi` by filename under guarded session-0 SSH, exports its JSON structure, calculates `model.sxo`, and exports a report. The model is self-built from K02, so the `.opi` extension is tested without claiming OPUS10-generated input content.

The native JSON export, event log and raw report are byte-identical to the accepted K02 run. Converter errors and notes are zero; warnings 108 and 126 are the same reviewed warnings. The accepted named Station structure, h8 mission launch, h11 success, and 72 half-hour system and stock rows are retained. `validate.py` and an independent read-only checker replay parent pins, the `.opi` copy, three guarded native steps and ten raw SHA-256 seals.

The native `.opi`, SXO, log and report bytes stay in ignored local `runs/` and are indexed in `evidence-index.json`. This demonstrates one direct-open common-format path. It does not demonstrate merging `.opi` and `.sxi`, OPUS10-produced data, `.opo` result points, LORA allocations, phase scenarios, GUI import or cross-engine parity.
