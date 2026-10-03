# E10.var09 overlapping ONDEM windows: negative conversion boundary, v1.0.0

This case uses the [accepted E10.var03 nonoverlapping ONDEM control](../E10-var03-ondem-support-gap-v1.0.0/README.md). The installed manual, physical pp. 335–336, prohibits overlapping transport policy periods. It tests a one-hour overlap as a **native input rejection**, not a simulation of transport behavior.

## Frozen input

The accepted control has `DOWN-POLICY` ONDEM windows h0–9 and h11–36, zero conversion errors, and an independently accepted physical timeline. The [negative input](native-input.json) changes only the first `DURN` from 9 to 12 hours plus `ProblemDescription`, creating h11–12 overlap while leaving the second window and every other model parameter unchanged. See the [pre-run contract](contract.json) and [exact diff](exact-diff.json). The converter was required to identify the policy overlap with a source-bound error; zero-error acceptance or unrelated failure would be NO-GO under that contract.

## Native diagnostic

Fresh guarded session-0 SSH run `e10-var09-overlap-v100-ssh-20261003-01` preserved active GUI PID 13340 under `Global\SimloxIssue18NativeQueue`. Import/export completed and retained all 22 authored populated tables exactly. The calculation process returned exit code **0**, but its conversion log reported **Errors 1, Warnings 1, Notes 0**: `TransportPolicyProfile` record 1, error **#153**, `FIX transports during ONDEM period in profile: DOWN-POLICY`. The only changed policy value makes its first ONDEM period extend across the second policy's h11 start, so the source-bound diagnostic supports a rejection of this overlapping profile. Warning #108 concerns enabled log volume.

The nominal SXO is only **4 bytes**; there is no simulation event log or JSON report, and the conversion log contains no simulation or result-saving marker. The calc exit code alone would misclassify this as success. No physical transport, inventory, resource, mission or terminal result is claimed for the negative input. The accepted zero-error E10.var03 control supplies the valid comparison.

This conclusion is specific to one h11–12 overlap, two ONDEM windows, one downward profile and the pinned installed SIMLOX version. It does not define ordering at a legal shared boundary, partial overlaps elsewhere, nested policies, GUI visuals or cross-engine behavior. Full E10, E11 and Issue #18 remain open. The raw diagnostic stays under ignored local `runs/` with SHA-256 seals in the evidence index.
