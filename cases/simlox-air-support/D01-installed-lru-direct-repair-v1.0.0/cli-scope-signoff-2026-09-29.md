# D01 installed LRU local loop: CLI scope sign-off (2026-09-29)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for this one-LRU, one-local-spare, local direct-item-repair variant. This sign-off does not accept remote supply, shortage, resource contention, explicit task breakdown, PM or alternate failure modeling.

## Frozen source and execution

The candidate derives from the accepted D01 system-direct input SHA-256 `d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450`. The six changed tables are recorded in [parent-diff.json](parent-diff.json); all other parent table values and schemas are unchanged. The new input SHA-256 is `eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93`, and the predeclared [contract](contract.json) SHA-256 is `6df812ebc72a4c147769809c0aca2af72fca7c19b8a60582f36c78919a217da9`. Installed SIMLOX executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; installed 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.

Native run `d01-lru-v100-ssh-20260929-01` used the verified session-0 SSH process, host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 guard. Import, export, calculation and report export each exited zero; the read-only import/export checker passed. The native conversion had zero errors and only warning 108 for enabled simulation logging. The sealed invocation SHA-256 is `bc2127040f36b59917608575729e4bcbeebe8efe8c9dbb6314c9c2175ec28f70`; closure SHA-256 is `3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0`. The closure binds all raw output sizes and hashes. Raw evidence remains in the ignored local `runs/d01-lru-v100-ssh-20260929-01/` directory and is not uploaded.

## Observed behavior

At hour 0, the local stock event shows one spare LRU on hand. A critical failure of installed `<TEACH-LRU-01,0,1>` at hour 9.8829 aborts the first mission. At hour 10, the system replacement demand takes spare `<TEACH-LRU-01,0,0>` from local stock, reducing on hand from one to zero. The system `SURP` task runs 10–10.5: `REMOVE` 10–10.25, `FIT` 10.25–10.5. The aircraft is ready at 10.5. The removed LRU enters local item `DIRP` at 10.25, completes its fixed one-hour turnaround at 11.25 and returns to stock, restoring on hand to one. Missions ending at 22 and 34 succeed.

The raw event log SHA-256 is `b5f0449114d1c4b4aaaeb959f3a75ddde0bae8d9530b14531c3a83087a95fa91`. The raw JSON report SHA-256 is `3a2049c44174391bb92b55cb1ccdc0c624231ec75fc5bbac60f7816107d5a911`. It contains 72 aligned half-hour system and stock intervals, one failure, one completed system repair, one repair interval, one stock-demand interval, no backorders, terminal ready aircraft and mission success fraction approximately 2/3. Compared with the accepted system-direct D01 report, the system interval rows differ only at 33.5, 34 and 34.5 hours because this LRU run has no second failure. The seed is a repeatability control for this executable, not a cross-version guarantee of timestamps.

## Review and limits

The [author replay](review/author-native-validation-2026-09-29.json) passed 64 checks with no differences. Its source SHA-256 is `4d61fa9dcccea61ca492731084a03be034a94fedbf906684211d0aaa22384e46`, and its report SHA-256 is `ea6053901ca34e54090084bf9d78dcbd3da8167dee7e6b2cceaccde411a8d17c`. A separate reviewer completed [static review](review/static-review-2026-09-29.md) before native execution and [read-only native replay](review/independent-native-review-2026-09-29.json) afterward, also with no differences. The independent report SHA-256 is `c98884823cd4a68113f4d19d8138f610f7ed5b2076a5ee02a979590a32063d06`. The independent replay checked source/diff/hash closure, session/GUI guards, conversion and roundtrip identity, component and stock event chain, and report aggregates.

The event log provides exact item identity and stock levels; the exported report has aggregate half-hour ledgers. This publication establishes the stated CLI behavior on the pinned executable. It does not establish GUI visual state or the broader D01/E01/E05 variants.
