# G01.var04: structural ASSY around a replaceable LRU

This bounded CLI case derives from the accepted [G01.var01 LRU/SRU chain](../G01-var01-lru-sru-v1.0.1/cli-scope-signoff-2026-10-01.md). The [contract](contract.json) and [native input](native-input.json) were frozen before the guarded native run. [Exact parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md) and [evidence index](evidence-index.json) define its accepted behavior and limits.

The physical `ItemStructure` is aircraft→ASSY→LRU→SRU, while `ItemReplacement` links the aircraft directly to the LRU. The ASSY carries only identity, description and type; it is never stocked, demanded or repaired. The local LRU/SRU logistics and mission schedule are inherited.

Run `build.py` to verify the frozen input from its parent, `describe_diff.py` to verify the four-table delta, and `validate_native.py runs/g01-var04-assy-v100-ssh-20261001-01` to replay the author assertions. The separate [read-only review](review/independent_readonly.py) replays raw evidence without importing the author validator. Native SXI/SXO, logs, report, invocation and closure remain under ignored `runs/g01-var04-assy-v100-ssh-20261001-01/` and are not uploaded.

Only one ASSY wrapper, one LRU/SRU chain, one base and one fixed seed are covered. Other ASSY positions, quantities, failure branches, GUI rendering and cross-engine equivalence remain unverified.
