# D04.var01 v0.1.1 independent contract review

**Verdict: GO_CONTRACT_ONLY.** The corrected contract preserves the prior one-cell OPHOURS threshold hypothesis and explicitly requires the missing D03 input byte pin in the later runner. This verdict does not approve the copied implementation or a native launch.

## Source and version checks

- Reviewed v0.1.1 contract SHA-256 `a49bd85018977531f8219f2f5fc5e1ebdfa8b5054eb2dc28d54f903ee950b8bd`.
- Its preserved v0.1.0 contract SHA-256 `0ee824f2ccc35319f8cd369d961099ecaf3258641f424bdbd875b69af1ce6450`, independent contract GO `d7b0cd954ed860f5ef31b2283b450b63945648143ef3df87cdf35d46a90dfec8`, and independent prelaunch NO_GO `0e2e1b99f47257e2bec9840390aa45bf9a5ae3f3e576fa65941b81b58108e35b` match the preserved files. The old and newly reserved run paths are absent; no v0.1.0 native result is claimed.
- Both v0.1.0 and v0.1.1 authored child inputs are byte-identical, SHA-256 `cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd`. The accepted D03 prerequisite input matches the contract SHA-256 `5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32`.
- The business question, accepted D04 parent pins, manual/executable pins and rules, one-cell `MaterielPM.PMINT` 3→4 OPHOURS delta, mission schedule, no-PM event and report gates, 120-row System/Stock checks, 11 ResultSummary fields, and integrated flight 3/ready 55/available 60/PM 0 predictions are unchanged. The new contract adds only version/failure provenance, a new run ID `d04-var01-op4-v011-ssh-20261006-01`, and explicit accepted D04 and D03 input/signoff source pins before and after native steps.

## Separate prelaunch gate

The v0.1.0 runner remains excluded because it omitted the D03 input pin and seal. The v0.1.1 package currently contains implementation files, but this memo evaluates only the contract. A fresh review must verify that its final runner literally checks D03 input SHA-256 and records it in both source seals, uses the v0.1.1 run ID and schema, preserves the exact child input and one-cell diff, and maintains the SSH0/mutex/protected-GUI and failure guards. The child label `OP3` and description “Three-operation-hour service” remain historical labels; PMINT=4 is authoritative. Raw native report bytes must be preserved while any trailing-comma normalization is confined to a parser copy.
