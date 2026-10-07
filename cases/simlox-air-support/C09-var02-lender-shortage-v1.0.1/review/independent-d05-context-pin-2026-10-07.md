# Advisory D05 PM-wait context pin

This receipt pins an **accepted contextual control**, not a C09.var02 parent, prerequisite, or addition to the frozen contract's 117 raw / 78 source dependency set. It supports parser/state calibration only. Accepted D05 signoff classifies run `d05-pilot-v100-ssh-20260930-03` as a bounded one-worker critical repair versus two **noncritical** calendar-PM competition.

| Record | Disk bytes | Disk SHA256 | Published Git bytes / SHA256 |
| --- | ---: | --- | --- |
| `D05-maintenance-competition-v1.0.0/native-input.json` | 44,306 | `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad` | 44,306 / `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad` |
| `D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md` | 6,342 | `e645b900f397a955d2b588aa5f0e4d50f2f4b7d082a09f35e7b89a4dfaf23c11` | 6,342 / `e645b900f397a955d2b588aa5f0e4d50f2f4b7d082a09f35e7b89a4dfaf23c11` |
| Accepted `runs/d05-pilot-v100-ssh-20260930-03/model.log` | 14,580 | `daeacfda91304217c1e3ac75e6842bd17de5ae2bac067fbf21aff82f96396fd5` | Local ignored raw; not published |
| Accepted `runs/d05-pilot-v100-ssh-20260930-03/report-raw.json` | 148,333 | `46975e779235a773b6e3473423dbb83a635cee9afd43baa77bb748f873cc406c` | Local ignored raw; not published |
| Accepted `runs/d05-pilot-v100-ssh-20260930-03/closure.json` | 5,254 | `4ade4062f3ef3a25d8adc96b9f57f5ca34eea850de2fd2a304a4e0163fb55736` | Local ignored raw; not published |
| Accepted `runs/d05-pilot-v100-ssh-20260930-03/invocation.json` | 6,966 | `32ca39008d2465e5c8de97bc69511131be7782e7a7b078706075ea42245285b0` | Local ignored raw; not published |

The two published files have **identical local and Git bytes**, verified separately. In the raw log, a noncritical PM task object starts h24 and its subtask fails resource availability; the worker is granted h28 and active work runs h28–29. Sampled SystemResults rows h24–27.5 have `NSYPM=0`, `NSYWR=0`, `NSYRY=1`; `NSYPM=1` during h28–29 performance. This calibrates the distinction between a pending task object and physical work. It does not predict the state of the v1.0.1 HOME PM, whose `DTIM=0` makes the due PM critical under installed manual pp204/373.
