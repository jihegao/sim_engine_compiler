# A14 simultaneous continuous-dependence diagnostic (v1.0.0)

**Decision: NO-GO for the frozen MUTD/deadlock hypothesis.** This package is retained as a reproducible native diagnostic and is absent from the publication index.

The accepted A05 continuous input SHA-256 997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea is the exact parent. [The contract](contract.json) and [the exact diff](exact-diff.json) were frozen before four guarded session-0 SSH runs. The diff SHA-256 is 2f83700fdc5f094adb471359ca6cc720f0e84b5a39d21fcfa2502cd9e7da75d8. Two independent one-aircraft continuous missions are scheduled at hour 8. Control has no dependency; one-way has one ordinary CONTINUOUS row; mutual has one MUTD=Y row; opposing has two reverse ordinary MUTD=N rows. Each source model imported/exported all 13 or 14 populated business tables exactly, converted with zero errors and warnings #108/#126, and produced a nonempty native report. The GUI PID 13340 survived all four runs.

| Variant | Immutable run ID | Closure SHA-256 | Event-log SHA-256 |
| --- | --- | --- | --- |
| Control | a14-control-v100-20261001-01 | 4ed4d219d960ca6add8a785195eb4c6773d6ec8785f475cb2d11b34fe0c0559e | e3fa74c72b82e9ba3fbceb021a391d74efd5b07f50a71c536bafffc191fd212d |
| One-way | a14-oneway-v100-20261001-01 | 9e3ce860d06a23980955159e26f93c0a98ec55fba4d79df1ed79e787e20e6edf | 13cec0a3abcbe30747b0c93eb2903266b46370195fb7835f112b5d5097d79559 |
| Mutual | a14-mutual-v100-20261001-01 | 0399fd786f86dfae3609e404896c25928879e98dd88874ba48fd563f189f007e | 1043150b1e550ec13e5645ffe2939c2c41ea8a34da2347ec32717efee16e32a2 |
| Opposing | a14-opposing-v100-20261001-01 | 8ee71699155516be3b10c037b94cccc31d004ad466e1ff3e9ba5263839a567d1 | 1043150b1e550ec13e5645ffe2939c2c41ea8a34da2347ec32717efee16e32a2 |

The two opposing rows did **not** deadlock: both missions launched at hour 8 and operated through hour 12. Its event log is byte-identical to the MUTD=Y variant. In both, SUPPORT succeeds at hour 12 while EXECUTE aborts at the same timestamp. The one-way variant also aborts EXECUTE at the coincident end. Thus the manual's deadlock contrast was not observed under this schedule; no general claim about MUTD, deadlock, or same-timestamp completion ordering is accepted. Raw runs remain in ignored local runs/ directories, with their invocation, input, model, report and closure hashes sealed.

The corrected [v1.0.1 slice](../A14-continuous-end-abort-v1.0.1/README.md) separates predecessor and dependent end times. The broader A14 method remains open.
