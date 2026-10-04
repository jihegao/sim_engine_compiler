# D12.var03 v1.0.1: excluded no-exposure diagnostic

This frozen N/Y candidate differs from [v1.0.0](../D12-var03-enfnc-v1.0.0/README.md) only by removing the h20 and h32 mission rows that exceeded its 14-hour horizon. The arms still differ only in description and `PM9P9.ENFNC=N` versus `Y`.

The guarded session-0 SSH run `d12-var03-enfnc-v101-ssh-20261004-01` preserved GUI PID 13340/session 1. Both arms completed all eight native steps with zero converter errors and warning #108 only; their event logs are byte-identical, SHA-256 `cce0c1dd71ad2f5175bd6f3737244c94d4d1635c06908611cbec3553b008cef3`. Native logs show the noncritical PM working 10–11, but no failure occurred in the 14-hour window. [Closure](runs/d12-var03-enfnc-v101-ssh-20261004-01/closure.json) SHA-256 `f5dd3a62bb88783093fe75cf24dabb9556c86f1ec85f441b99ae10a6534dc3e0` seals 22 local raw files listed in the [evidence index](evidence-index.json).

**Status: excluded diagnostic.** There was no competing noncritical repair, so identical arms cannot support an ENFNC claim. [v1.0.2](../D12-var03-enfnc-v1.0.2/README.md) raises the explicit failure frequency equally in both arms to establish the required exposure; this source and run remain immutable.
