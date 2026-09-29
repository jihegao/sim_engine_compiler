# A02 1.0.0: bounded CLI behavior sign-off, 2026-09-29

This is a later, read-only case review under PR #44's revised Issue #18 standard. The frozen source, input, manifests, acceptance file and native runs remain unchanged.

## Decision and scope

`native_behavior_accepted_cli_scope` and `reusable_published` for the normal one-aircraft, three-scheduled-mission path from 0 to 36 hours. Its accepted parent is the [A01 bounded normal path](../A01-single-aircraft-single-mission/cli-scope-signoff-2026-09-29.md). This decision supplies the repeated-wave behavior prerequisite for A03; it does not pre-accept A03's two-aircraft behavior.

The A01 input SHA-256 is `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`; A02 input SHA-256 is `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`; A02 contract SHA-256 is `f192c22de44ec20cf8581e2652ce8b4a44fc315acb7998624be340cb5a42a465`. The exact parent diff adds only two `OperationProfile` rows at 20 and 32 hours; the inherited 8-hour row, all aircraft/mission identities and every other table remain. The [independent read-only review](review/independent-readonly-2026-09-29.json) recomputed this delta from both checked inputs.

## Sealed native evidence

Raw runs remain under `C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\`:

| Run ID | Invocation SHA-256 | Closure SHA-256 | Native log / raw report SHA-256 |
| --- | --- | --- | --- |
| `a02-bound-final-20260927-03` | `45a5b918d2429476399ddbde9a2e166815b6ba8e9a09d8906b3ef13ecbb3e87d` | `fc0cc2d0578d2e8d126e79886ab2ba72238a725aea86c361ede6d48dadc6a69a` | `5101ef9157f941627a2851774d884f9ec5abe92af894af0c177221749eca66ba` / `a7227687988841c074b28b524792af7d856cd674840169bf15c210f2d2cd4739` |
| `a02-bound-replay-20260927-04` | `10c3f7784073260e875e001a711788c593c14a5a52b462ab6bdef81528e92076` | `9a44bc9f5d52cfd2178545315b6cd9b380585e98c36502025b329e380f1909d1` | same log and report bytes |

The independent reviewer checked all 17 indexed files in each run against size and SHA-256 and the 12 raw files sealed by each closure; no mismatch was found. Both original invocations bind the input, schema, contract, parameters, generator, validator, runner, binding module and SIMLOX executable. The original `validate_native.py --read-only --case A02` returned `cli_behavior_verified` with empty differences for both runs. Four native steps exited 0, conversion recorded no errors and only explained warning IDs 108/126, and all 10 nonempty business tables matched the native JSON roundtrip.

Three distinct mission instances were ordered at 7, 19 and 31 hours, launched at 8, 20 and 32, and completed at 10, 22 and 34 on the same aircraft. No mission was cancelled or aborted. Every run has 72 contiguous half-hour SystemResults intervals, six aircraft-hours of mission operation and `NPSTA=0`. The final and replay SXI, native log and report are byte-identical; their SXO hashes differ, so no SXO-byte equality is claimed. The independent review binds each invocation to the unchanged frozen contract and passed with zero differences; its JSON SHA-256 is `441cbaf31c4bedb170fcfd683a2427153c3a67b36bdebd200162280122c75288`.

## Reproduction and limits

The [A02 README](README.md) gives the frozen input SHA and fresh-run procedure. Its historical runner rejects an active SIMLOX process, so this review only replayed sealed evidence and did not disturb GUI PID 13340. The GUI observations in [the dated addendum](../gui-acceptance-2026-09-29.md) corroborate displayed charts and selected report rows but are optional under the revised policy; they do not rebind or modify the CLI artifacts.

This always-ready path does not test deadline priority, before/at/after cancellation, a mission crossing `SIMPE`, faults, preparation, shared resources, GUI-only behavior, Python/Rust/J35 equivalence or performance. Those claims remain outside A02 publication.
