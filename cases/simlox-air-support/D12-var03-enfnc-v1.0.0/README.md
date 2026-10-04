# D12.var03 v1.0.0: excluded converter diagnostic

This frozen N/Y ENFNC candidate derived from the accepted D08.var03 explicit noncritical failure input. It added a 9.9-hour noncritical PM and one shared maintenance worker, then shortened the simulation horizon to 14 hours while retaining the parent's mission rows at hours 20 and 32.

The guarded session-0 SSH run `d12-var03-enfnc-v100-ssh-20261004-01` preserved GUI PID 13340/session 1. Native input conversion in the first N arm reported **error #204** because missions may not return before the simulation period ends. The runner stopped before accepting an SXO or running the Y arm. [Closure](runs/d12-var03-enfnc-v100-ssh-20261004-01/closure.json) SHA-256 `a3815862f60e0a45e1f564de99a6332570ed7b627a853caf26246cfd698e1aa3` seals the 10 local raw files in the [evidence index](evidence-index.json).

**Status: excluded diagnostic.** No ENFNC behavior is inferred. [v1.0.1](../D12-var03-enfnc-v1.0.1/README.md) corrected the out-of-window mission rows in a new package; this source and run remain immutable.
