# D12.var03 ENFNC post-run static review — 2026-10-04

**GO for the bounded N/Y physical work-order contrast.** This review was read-only; I did not invoke SIMLOX or change authored source or native output.

The accepted D08.var03 input/closure/sign-off and D05 maintenance-pattern pins match the contract. Both v1.0.2 inputs match frozen hashes; the pair differs only in ProblemDescription and `MaterielPM.PM9P9.ENFNC` N versus Y. The common 14-hour source retains only the h8 mission and raises `FM-POS-A.FRQ` equally in both arms. Contract and runner hashes match the unchanged before/after source seals.

Closure SHA-256 `3f9a9c57ee6b99614adeb375775abd18cc8a029cb9a82b4d444b0a039e07c8d0` has no error. All 22 local raw file size/hash seals match the closure and evidence index; eight import/export/calc/report steps exited zero and recorded GUI preservation. Both converters report Errors 0, Warning #108, Notes 0. The v1.0.0 converter-#204 closure and v1.0.1 no-failure closure match the contract's excluded-diagnostic pins. Author replay is GO 133/133 (verdict SHA-256 `0f6fffb60db4eeb9510fb6e9a1073432be8f660679f644265c15babb1d8f55b2`); independent replay is GO 1,267/1,267 (verdict SHA-256 `30e9c36ba8dcaba83569b38cfda1871969886762c795a6375a49f379da43dd68`).

Both native logs show the same noncritical `FM-POS-A` fault at hour 8.31325 and mission success/return at hour 10. PM and CM **task-start events both occur at hour 10 in both arms**. With ENFNC=N, the PM subtask books the sole worker and performs 10–11, then CM performs 11–11.5. With ENFNC=Y, CM performs 10–10.5, then PM performs 10.5–11.5. The evidence therefore supports a physical work and resource-booking order difference, rather than a difference in task-start timestamps.

Each raw report has 28 half-hour System, Resource and Stock bins. Direct integration gives one PM hour, half an hour of repair, and 1.5 worker-hours per arm; each has one PM start/completion. The differing System and worker bins at 10–11.5 match the event work spans, while summary and terminal outcome remain equal. README and sign-off state this narrow claim accurately. The log establishes PM pending at return but does not directly expose the internal h9.9 due or counter state.

**Limits:** One fixed seed, one aircraft/base/worker, one explicit noncritical mode and one PM, with a deliberately elevated failure rate. No general priority or rate law, critical-task behavior, PMRID, counter reset, remote-base, GUI or cross-engine claim follows.
