# C05.var03 v1.0.1 draft validation protocol — NO_GO_PROTOCOL

This is a separate finding on the same unapproved validator draft `validate_native_cli.py`, 15,965 bytes, SHA-256 `6199217e26e690dffd1c38ae1778f0931a340770b96c5d406d80513235924c48`. It supplements the preserved draft-source and draft-validator NO_GO memos. No native run or manifest approval had occurred.

The draft `validate()` unconditionally invokes `child_seals()` before its behavior checks. `child_seals()` requires a final `closure.json` and six completed stages including `check_behavior`. If the native runner invokes `check_behavior` before final closure sealing, this gate cannot pass on a correct live run: its own stage has not finished and closure does not exist yet. The runner and checker need distinct, explicit modes:

- **Live behavior mode** may inspect the copied input, frozen contract/source identity, converter and report raw artifacts, and the first five completed stages. It must verify current SSH0/GUI/mutex lineage directly from invocation/steps rather than claiming a final closure.
- **Sealed postrun mode** must verify invocation identity, source before/after, all six completed stages, final closure and every declared raw SHA/size seal; it must re-evaluate behavior from the same immutable raw without a native call.

The draft also hardcodes one h7 crew booking and at least one reconfiguration start for the radio arm. The frozen contract permits **zero or one** partial A booking and requires tracing reconfiguration only when observed; a B radio shortage can occur before reconfiguration. The negative gate must reject every mission launch, including a one-system launch, because the source minimum is two with one A and one B. Converter attribution must bind each of the three #2053 diagnostic lines to its particular item and record, rather than finding all three item names anywhere in the log.

Recovery is a new, byte-pinned validator/runner bundle with honest live and sealed modes, source-conditioned partial ledgers, contextual diagnostics and pure negative fixtures. Preserve this draft and these findings as excluded prelaunch evidence; no native launch approval is conveyed.
