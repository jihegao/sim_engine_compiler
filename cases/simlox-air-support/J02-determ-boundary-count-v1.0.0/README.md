# J02 deterministic and boundary mission counts

This bounded package covers catalog variants `J02.var01` and `J02.var04`
against accepted `J02.var02@1.0.0` seed 01. Its five native inputs change
only the quantity distribution, one seed, or deployed-aircraft capacity.
`build.py --check` verifies the parent SHA-256 and each exact field diff.

The common model keeps random initiation with `IPER=0`, `IDISP=EQUIDIST`,
hour-8 starts, one-hour notice, two-aircraft formations, two-hour missions,
and hour-36 horizon. A single `IntegerDistributions` row has `PFAC=1`,
`BASED=<DETERM>`, `DISTID=COUNTD`, and `PARAM1` equal to 0, 2, or 4.
`OperationProfile.IQTYD=COUNTD` overrides its retained `IQTY=1`. Two count-2
inputs differ only in `Control.RSEED`. Count 4 is run with eight and six
deployed aircraft so the six-aircraft shortage can be isolated.

| Arm | Demand | Aircraft | Native outcome |
| --- | ---: | ---: | --- |
| `determ-2-seed-01` | 2 | 6 | Two successful formations |
| `determ-2-seed-02` | 2 | 6 | Two successful formations |
| `zero-six` | 0 | 6 | No mission activated or launched |
| `four-eight` | 4 | 8 | Four successful formations |
| `four-six` | 4 | 6 | Four activations; three successful formations and mission 4 cancelled at hour 8.33333 |

Five excluded diagnostic runs froze these expected observations. Five fresh
accepted runs, with IDs ending `-accepted-20261001-01`, each used the guarded
session-0 SSH runner, host-wide `Global\SimloxIssue18NativeQueue` mutex, and
preserved GUI PID 13340. The runner binds input, parent, installed manual,
dictionary, executable, validator, and source hashes before execution; it
seals raw outputs even on partial failure. Run each arm with a fresh `-RunId`,
matching `-Arm` and SHA-256 from `contract.json`, and `-AllowExistingGui`:

```powershell
ssh -tt -o BatchMode=yes localhost 'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\J02-determ-boundary-count-v1.0.0\run_native_ssh.ps1" -RunId j02-four-six-accepted-20261001-02 -Arm four-six -InputSha256 ce351b9117c701d56cec3dad9c89bd32dafbf9ad78e927b2b4f43f632c6c0962 -AllowExistingGui'
```

`validate.py RUN_DIRECTORY ARM` replays a single run without SIMLOX;
`validate_panel.py` checks the accepted matrix. Local `runs/` is ignored by
Git; `evidence-index.json` records accepted run IDs and raw SHA-256 seals.
The installed manual and dictionary are fingerprinted in `contract.json`
without uploading proprietary files. Relevant manual pages are 271, 273–274,
and 542.

The result establishes the five fixed-input native outcomes only. Two seeds
do not prove deterministic invariance for every seed. This one capacity
boundary does not characterize other shortage policies, GUI-only behavior,
other distribution mixtures, or cross-engine parity. `J02.var03` POISSON
remains separately scoped.
