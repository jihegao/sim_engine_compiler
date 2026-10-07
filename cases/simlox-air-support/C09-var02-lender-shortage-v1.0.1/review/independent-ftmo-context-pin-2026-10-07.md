# Advisory mixed-unit FTMO context pin

This is an accepted **calibration control**, not a C09.var02 prerequisite or addition to the frozen dependency set. Installed manual physical pp642–643 defines FTMO as the mission-operation fraction averaged per system at an operational unit. Accepted G03.var03 has two different deployed SIDs in separate units, each assigned the same fixed mission profile. Its aggregate SystemResults at h8 has `NSYMO=2` and `FTMO=1`, not a sum of two per-SID fractions. Accepted A03 three-available has three deployed aircraft, two flying at h8 and aggregate `FTMO≈2/3`. Together these controls support a fleet-average rather than a sum-of-groups interpretation. The new HOME SID/unit is a nonparticipant, so the prospective oracle should derive its aggregate denominator from all systems in the queried report group and the new source; it must freeze that choice before native output and fail rather than switch formulas postrun.

| G03.var03 record | Disk bytes | Disk SHA256 | Published Git identity |
| --- | ---: | --- | --- |
| `native-input.json` | 45,273 | `42f3d9db9b201b80314731091e3f3e1ea6b5dfefdc40addca5f75f33daf13c7f` | 45,273 / same SHA256, byte-identical |
| `cli-scope-signoff-2026-10-03.md` | 2,079 | `4df1f0ff99f89d739ec3febc282eb263625af94302854312131b19382dd3c49a` | 2,079 / same SHA256, byte-identical |
| `runs/g03-var03-simultaneous-v100-ssh-20261003-01/model.log` | 17,199 | `68d4f9d07beb03eb4722e400082e51595e3d3bd730b52558a7c31bfe65408d69` | Local ignored raw; not published |
| `runs/g03-var03-simultaneous-v100-ssh-20261003-01/report-raw.json` | 103,965 | `09eda38bcd1bce9c5b9a396bbce426f8b27ed076b0744dc10f7aadc41ea619ab` | Local ignored raw; not published |
| `runs/g03-var03-simultaneous-v100-ssh-20261003-01/closure.json` | 7,620 | `bfbd9a4bddc99d59509baea73b8a4ce8c7015d73b7ba7b45b24bb7d503a0be04` | Local ignored raw; not published |

The two published source records were independently read from local disk and `HEAD` Git blobs. This control does not itself prove how SIMLOX groups the new HOME unit; the frozen C09 contract's full-cell check remains decisive.
