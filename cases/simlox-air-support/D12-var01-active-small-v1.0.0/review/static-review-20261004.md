# D12.var01 active-small post-run static review — 2026-10-04

**GO for the bounded CLI observation.** This review was read-only. I did not invoke SIMLOX or change frozen source or raw evidence.

The accepted D12.var01 v1.0.1 unlinked/linked inputs, closure and sign-off match the frozen parent SHA-256 pins. Each new arm makes the declared nine-cell parent change to move the larger PM from hour 47 to 48.5 and rename its references. The new arms differ only in descriptive text and `BIG48P5.PMRID` null versus `CAL24`. Contract SHA-256 `0df253d5357b336dc2ee1c69b550c01f0193f5b1413b903a1710c21a7f3faea1` and runner SHA-256 `951a13c6d8f227c624e0a32c3c1f8e5a50b736a67c4e860243bd00c6c5bfe1f3` match the closure's unchanged before/after source seals.

Closure SHA-256 `2139f7097f58c42a93c7469d4fda4ad65efc1cbcb08150573ae20692def3e87c` has no error. All 22 raw file size/hash seals match both closure and evidence index. The eight import/export/calc/report steps exited zero and recorded GUI preservation in session-0 SSH under the host mutex. Both conversion logs show Errors 0, Warnings #108/#126, Notes 0. The author validator's 165/165 verdict checks the exact source derivation, populated native roundtrip cells, task events, worker leases and report bins; I inspected that logic and separately checked the raw event trace and report totals.

Both arms show `CAL24` task 3 start work with the only worker at hour 48 and `BIG48P5` due at 48.5. In the unlinked arm the small subtask performs through hour 49, and the other small task works 51–52. In the linked arm task 3 and its performing subtask receive stop events at 48.5 after half an hour of work; its worker is released and immediately booked by larger task 5. The other small task is stopped while waiting at 50.5. The linked log also prints task-completed lines for stopped tasks, so completion must be interpreted with the report counters and work events. Native `SystemResults.NPMT` is 6 unlinked versus 4 linked.

Both reports have 120 System, Resource and Stock half-hour rows. Direct sums give PM aircraft-hours 6 versus 4.5 and worker-hours approximately 11 versus 9.5, including the common five repair hours. This reconciles the 1.5-hour PM work reduction. The event-log worker bookings do not overlap. The sign-off accurately bounds the claim to a physically performing small PM stopped in this one model; its wording distinguishes a stop event from unobserved internal counter reset.

The separate independent replay now reports GO 3,281/3,281 with verdict SHA-256 `9f38576eb7f729d1c904a9c2129978ce4ea4a32b33d1193bb65a6906a4d17313`. Its conclusions match the event and report evidence above.

**Limits:** One seed, two aircraft, one base, one worker and CALHOURS PMs. This does not establish a general priority law, multi-level PMRID, ENFNC, remote-base behavior, GUI behavior or cross-engine equivalence.
