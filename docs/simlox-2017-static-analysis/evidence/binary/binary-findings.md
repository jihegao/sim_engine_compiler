# 独立汇编核对笔记

下方为普通 PE/Capstone 解析笔记，不是 REA Evidence。笔记中的 JSON 文件名指原分析机器保留的源文件；这些独立解析文件未随本 PR 上传，其哈希列在[来源清单](../../provenance.json)。可在[REA 审阅摘出](../rea/function-observations.json)中独立核对对应地址的 Ghidra 汇编。

# Static assembly finding ledger

Target: `C:\Program Files\Systecon\SIMLOX\Simlox.exe`, SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

These are read-only parser/Capstone observations, not REA Evidence records. REA decompilation in the parent investigation can independently corroborate them. No target code was executed.

## Observed: two levels of random generation

- `0x140d8e3b0` updates a 32-bit state using `imul ..., 0xc8c27395`, clears bit 31 using `btr`, writes the state back, converts the unsigned value to double and multiplies by `2^-31`. Thus `x_next = (1220703125 * x) mod 2^31`, `U = x_next / 2^31`. `1220703125 = 5^13`; the encoded 32-bit immediate is `3368186773`, equivalent modulo `2^31`.
- `0x140c4aa00` calls that function on `simulation + 0x10` and returns `lower + U * (upper - lower)`.
- Normal (`0x140d8e6c0`) and lognormal (`0x140d8e550`) kernels inline the same update and constants `-2`, `2^-31`, `6.283185307`; three scalar math call sites form the log/square-root/cosine pattern. Static mathematical inference: Box–Muller. Only the first update is persisted; the second variate is computed from the next state locally. This does not establish distribution quality or runtime usage of every distribution.
- Normal subclass slot 11, `0x140e47db0`, calls the kernel once and sets every result failing `result > 0` to zero. There is no rejection/retry loop in this complete short function. This supplies direct binary evidence for clipping negatives, to compare against the parent's manual evidence (manual interpretation itself is outside this ledger).
- Mersenne Twister seed handler RTTI and slot 0 connect `0x140ea97c0` to `0x140ea9700`. The latter contains `624`, `1248`, twist `0x9908b0df`, and tempering shifts `11/7/15/18`. Static inference: MT19937-family output for seed allocation. This coexists with the Lehmer sampling kernel; naming alone would not have revealed the distinction.

Sources: `sampling-disassembly.json`, `prng-disassembly.json`, `rtti-candidates.json`.

## Observed: replication seed reaches sampling state

- `0x140ea9830` locks handler mutex at `handler + 8`; checks cancellation flag `+0x1c` and count `+0x18 < +0x10`; uses original seed `+0x14` for the first allocated replication, otherwise calls handler virtual slot 0; writes the seed through output `r8`; increments the count and writes replication index through `r9`.
- Worker `0x140de2ba0` requests this allocator at `0x140de2c94` and `0x140de30db`. The seed output is stack local `rsp+0x60`, and replication output points to shared loop-data `+8`. The worker separately handles already allocated first work using loop-data `+0x28`.
- Worker places the seed as the fifth argument to `0x140c461c0` at `0x140de2ffd` / `0x140de3153`. The callee loads it from `rbp+0xf0` and writes `simulation+0x10` at `0x140c46234`, matching the sampling wrappers' state pointer.
- The constructor writes vtable `0x14179acc0`; its COL leads to RTTI `.?AVCSimData@@` at TypeDescriptor `0x141d085d8`.
- Worker executes each replication through `0x140c49300`, then reads the final 32-bit state through `0x140c489b0` and passes it as `edx` to the seed allocator for later work. The observed Mersenne Twister slot-0 wrapper ignores that `edx` value; whether other seed-handler implementations consume it remains unknown.

Sources: `worker-disassembly.json`, `seed-assignment-disassembly.json`, `rtti-candidates.json`.

## Observed: event calendar execution

- High-level simulation wrapper `0x140de13f0` calls orchestrator `0x140de35b0` at `0x140de15a3` between the starting-simulation and elapsed-time messages.
- Orchestrator binds worker address `0x140de2ba0` at `0x140de388b`, creates thread tasks and joins them. Its worker count is limited by available hardware/configuration and replication count; exact business semantics await REA decompilation.
- `CSimData` run wrapper `0x140c49300` stores duration `xmm1` to `+0xc0`, loads calendar pointer from `+8` and tail-jumps to `0x140d8e9d0`. That creates a stop event with integer field `0x80000000` and an additional large double tie-break value, then tail-jumps to the event loop `0x140d8e8f0`.
- That loop is split over three PE runtime-function ranges: `0x140d8e8f0..0x140d8e903`, `0x140d8e903..0x140d8e998`, `0x140d8e998..0x140d8e99e`. These are portions of one control-flow function, not three independent methods.
- Within the loop, `0x140d8e390` supplies the next notice candidate; notice `+0x18` is copied to calendar `+0x20`; the associated object pointer from notice `+0x30` is stored to calendar `+0x10`; the notice is unlinked by `0x140e970f0`; associated object's virtual slot `+0x10` is called; then the notice is cleaned up. The loop repeats while stop flag calendar `+0x68` remains zero.
- `event_notice` comparator `0x140d8ea60` orders by double `+0x18` ascending, then signed integer `+0x20` descending, then double `+0x28` ascending. These field offsets/order are observed; names such as priority and creation time are interpretation pending surrounding-code evidence.
- Other `event_notice` slots: `0x140d8e510` returns time `+0x18`; `0x140d8e220` formats a log string; `0x140d8def0` is a deleting destructor. Event processing is through the associated object's virtual method, not through the notice vtable.

Sources: `event-wrapper-disassembly.json`, `event-order-and-thread-disassembly.json`, `event-run-entry-disassembly.json`, `event-calendar-loop-disassembly.json`.

## Remaining unknowns

- Exact event callback types, cancellation behavior, all failure-generation algorithms, result aggregation and warm-up policy are outside this bounded pass.
- Function and data names other than recovered RTTI are inferred; function addresses and instruction operands are observations.
- This ledger supports static control/data flow, not actual execution, reachability under every model, or performance validation.


# Bounded TCLEV static verification

Source: Simlox.exe SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. Ordinary read-only Capstone/PE evidence, no target execution and no REA Evidence IDs.

## Observations

- `CSimResultController@SimResult` TypeDescriptor `0x141d0d2f0` -> COL `0x1418d6050` -> vtable `0x1417aefa8`.
- `0x140deb150` (slot 4) obtains input double through `0x140c8b3b0` and stores it to controller `+0x120`. It enables the continuous-check flag `+0x11c` only if the value is greater than `2.220446049250313e-16` (double epsilon), then emits the continuous-target-confidence-level message. This directly ties the flag/threshold to the input rather than to a hard-coded 0.1 or 0.5 value.
- `0x140deab70` (slot 3, result merge) updates the aggregated result, obtains a four-double metric vector through `0x140c896b0`, compares `threshold > vector[2]`, increments controller consecutive count `+0x128` on success and resets it to zero otherwise. Equality fails the strict comparison.
- `0x140deac70` (slot 7, continue decision) returns true unconditionally when continuous checking is disabled; otherwise returns `count < 10` using immediate `0x0a`.
- Orchestrator result-processing function `0x140de2250` calls merge slot `+0x18`, then continue slot `+0x38`. When continue returns false it calls `0x140ea9910`, which stores `1` into seed-handler cancellation flag `+0x1c`. Existing worker/allocator evidence shows this prevents further seed allocation; this does not prove already executing workers stop immediately.
- Metric entry `0x140c896b0` passes aggregate sample count to `0x140e5eff0`. The latter builds four metrics using `0x140e5e590`, pairing aggregate fields `+0xa0/+0xc0`, `+0xa8/+0xc8`, `+0xb0/+0xd0`, `+0xb8/+0xd8`. The continuous check selects the third pair (`+0xb0/+0xd0`).
- Complete short function `0x140e5e590` computes `sqrt(max((Q - n*m*m)/(n-1)/n, 0))/m` when `n > 1` and `m > 0`; otherwise returns zero. This formula is observed directly from arithmetic/branches, with the square-root call corroboration left to REA/CRT naming. Static interpretation: relative standard error if `m` is the sample mean and `Q` is the sum of squared observations.

## Interpretation and limits

The machine code supports ten consecutive successful relative-error checks followed by cancellation of new replication allocation. It corroborates the handbook's continuous-count rule. Exact business meaning of the third metric dimension and the identities of the mean/second-moment inputs require further source-field mapping.

The strings for warnings above 0.1 and 0.5 are referenced from input-validation metadata registration in large function `0x140c0c3a0`. Their actual validating comparisons were not followed in this bounded pass. No claim is made that numerical input-range checks at those values were machine verified.

## Stable evidence

| File | Functions |
|---|---|
| `termination-firstpass-disassembly.json` | `0x140de2250`, `0x140de1260`, progress accessors |
| `termination-controller-disassembly.json` | Complete merge `0x140deab70`, continue `0x140deac70`, output writer `0x140deac90` |
| `termination-threshold-setup-disassembly.json` | Complete continuous-check setup `0x140deb150` |
| `termination-metric-entry-disassembly.json` | Complete metric accessor `0x140c896b0`, seed cancellation `0x140ea9910` |
| `termination-metric-vector-disassembly.json` | Complete vector builder `0x140e5eff0` |
| `termination-relative-error-disassembly.json` | Complete relative-error arithmetic `0x140e5e590` |
| `termination-controller-constructor-disassembly.json` | Constructor `0x140dea920`, flag/threshold/count initialization |
| `termination-setup-disassembly.json` | Seed-handler construction caller `0x140de2020`; useful navigation, separate from TCLEV |
| `mt-seed-constructor-disassembly.json` | Complete MT seed-state initialization `0x140ddcd80` |

The replaceable scratch file `followup-disassembly.json` is not a stable source reference.
