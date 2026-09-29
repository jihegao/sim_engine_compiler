# D02.var06 traditional clock input matrix: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for the installed converter's rejection of four specific traditional clock inputs, with an accepted OPHOURS rate-table control. This result addresses only the D02.var06 predefined-value matrix.

## Source and frozen inputs

The accepted [D01 installed-LRU parent](../D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) input SHA-256 is `eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93`. Its traditional `Item.FRT=300000` and `Item.OPID=OPHOURS`, installed LRU, spare, seed, missions, repair and horizon stay fixed apart from the proposed clock row. The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The dictionary lists `OPHOURS` or a defined custom `OperationParameter` for traditional `Item.OPID` and `ItemFailureRate.OPID`. The manual and dictionary are not uploaded. Native conversion, not the source statement alone, determines the result below.

The [contract](contract.json) declared four rejection hypotheses and one positive control before execution. The [exact parent diffs](parent-diffs.json), SHA-256 `7c6d0aaedb83099e0e131efe7211262d018ed9d7c3a628c7e557d4ad84607bc5`, change only `ProblemDescription` and `Item` for item variants (29 other parent tables unchanged), or `ProblemDescription` and an added `ItemFailureRate` for rate variants (30 parent tables unchanged).

| Variant | Frozen input SHA-256 | Native conversion |
| --- | --- | --- |
| `item-calhours` | `e6287abc8e3292aeef8ac2b2ff30daecddcb998eb2659c4741690e70b9879239` | `Form: Item`, error #2057 for `CALHOURS` |
| `item-missions` | `99b3daaa36febae511e195c71f739dd34b23182f7c8e49f6db47b433b35c5dbc` | `Form: Item`, error #2057 for `MISSIONS` |
| `rate-ophours` | `b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797` | zero errors; #108 logging and #2058 override warnings |
| `rate-calhours` | `70ba834f4fb2c6bd2ba4558e1c499024652b533f297951e53445585925b9e713` | `Form: ItemFailureRate`, error #2057 for `CALHOURS` |
| `rate-missions` | `0fb2b7dd2761fe051d5ebc3c2c2cfdd957142c4f60db7c027efaa10a7c289262` | `Form: ItemFailureRate`, error #2057 for `MISSIONS` |

## Native evidence and independent review

Each run ID is `d02-var06-<variant>-v100-ssh-20260930-01`. Session-0 SSH, the `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 identity guard were used for each serial run. All five inputs imported and exported, preserving every populated source table: 18 for item variants and 19 for rate variants. The OPHOURS control completed calculation, report export and roundtrip checker, with 72 report bins, one failure and repair, and a ready terminal aircraft. Its warning #2058 reflects the intended duplicate base-rate override; its stochastic outcome is not a broader reliability claim.

The four negative inputs each have conversion `Errors: 1, Warnings: 1, Notes: 0`, with warning #108 and one form-specific #2057 error. The native calc process returns zero despite the conversion error and creates only a 4-byte `.sxo`. The runner records the missing usable simulation output as failure and stops before report export. This is native **input rejection** evidence, not a simulation of those four clocks. The raw invocation, steps, conversion logs, import/export artifacts and closures are retained locally under ignored `runs/`, with no proprietary manual or dictionary in Git.

| Variant | Local closure SHA-256 |
| --- | --- |
| `item-calhours` | `ed64d5c0d7cd953452a5d1e71088e8b61cc4b51dc8efc48562d8aa72c7b835e9` |
| `item-missions` | `d92b4d849f3a174c8de1503f534e47a22dc24344d44b98ec50ad66ff59c43b79` |
| `rate-ophours` | `1a23e4a341914673b5ea7e898094e22a2970176e94482868567f551862c02221` |
| `rate-calhours` | `c03c305150aec4d4d794ddf0baaaedad7ee6ad35a7e90f7162f0994769111879` |
| `rate-missions` | `709437f34497ca1bfcb776f7d87d05b2d695fdbeaba7f57da676538ea93c0692` |

The [author validator](validate_matrix.py), SHA-256 `286afd3bffec69cc61ce748a2ba0064283f41d2c3de5684345e837daa6dcaf34`, passes [178/178 checks](review/author-matrix-validation-2026-09-30.json), SHA-256 `964851ad6fbdec349a8d06da3c58968951e3905cd98f529b027e6af6a8a8406b`. A separate reviewer wrote a [read-only replay](review/independent_matrix_readonly.py), SHA-256 `da26f7e5d50e2ecf7c4b4d2ade0b8b17845902074bd8d2ed1c25b8def34c7058`, without importing the author validator. It passes [223/223 checks](review/independent-matrix-2026-09-30.json), SHA-256 `4357e5da3c8f87ee5b0d1e975ca87fcd9956c46b509139c36ca49137ca4c51b4`, including source/diff scope, raw seals, guarded invocations, roundtrips and exact diagnostics.

This acceptance is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. It does not test custom `OperationParameter` identifiers, other clock identifiers, other versions, zero exposure, alternative seeds, GUI visual content or cross-engine equivalence. [D02.var02](../D02-var02-failure-mode-calendar-v1.0.0/cli-scope-signoff-2026-09-30.md) separately accepts `FailureMode.OPID=CALHOURS`; that capability does not transfer to the traditional `Item` or `ItemFailureRate` forms. Issue #18 stays open.
