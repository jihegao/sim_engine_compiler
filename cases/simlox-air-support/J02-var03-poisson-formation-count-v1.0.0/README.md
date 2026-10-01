# J02.var03 integer Poisson formation count

This bounded case derives from accepted `J02.var02@1.0.0` seed 01. Its
`IntegerDistributions` row changes from `COUNT03/<IRECT>/0–3` to
`COUNTPOI/<POISSON>/PARAM1=1.5`, `OperationProfile.IQTYD` references
`COUNTPOI`, and deployment rises from six to twelve aircraft. The model
retains `RANDOM`, `IPER=0`, `IDISP=EQUIDIST`, hour-8 mission start, one-hour
notice, a two-hour two-aircraft formation, and hour-36 horizon. `IQTY=1`
remains in the input but native warning #211 says the custom quantity
distribution overrides it. Seeds 02–32 differ from seed 01 only in
`Control.RSEED`. `build.py --check` verifies the accepted parent fingerprint
and exact source diff.

Thirty-two excluded diagnostic runs fixed the observation sequence. Thirty-two
fresh accepted session-0 SSH runs reproduce counts 0–5, with frequencies
0:7, 1:13, 2:6, 3:4, 4:1, 5:1. The sample mean is 1.4375 and sample
variance is 1.5443548387096775. Each positive count launches that many
simultaneous successful two-aircraft formations at hour 8 and completes at
hour 10; a zero count activates none. In this selected panel, no seed asks
for more than five formations, so twelve aircraft suffice. Each report has
72 aligned System/Stock bins, four aircraft flight hours per mission, no
stock demand and twelve aircraft ready at horizon.

The native runner uses authenticated session-0 SSH, the host-wide Issue #18
mutex, exact source and installed manual/dictionary/executable fingerprints,
and a start-identity guard for GUI PID 13340. Each run records four native
steps and seals 11 raw files. The ignored local `runs/` directory holds the
raw evidence. `validate.py RUN_DIRECTORY SEED` replays one run without
SIMLOX; `validate_panel.py` checks the 32 accepted runs and descriptive
statistics. `evidence-index.json` records run IDs and SHA-256 seals. On a
clean checkout without existing `runs/`, run a seed with its matching hash
from `panel-diff.json`, for example:

```powershell
ssh -tt -o BatchMode=yes localhost 'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\J02-var03-poisson-formation-count-v1.0.0\run_native_ssh.ps1" -RunId j02-var03-seed01-accepted-20261001-01 -Seed 1 -InputSha256 2edd37fb063ac7f1d5a1ee17ea10779ac699fce75f4288e81b4026a3ff8a933f -AllowExistingGui'
```

The installed dictionary permits `<POISSON>` in `IntegerDistributions` and
a user distribution reference in `OperationProfile.IQTYD`; the installed
manual discusses random initiation and integer distributions on pages
271–274 and 541–543. Proprietary sources are SHA-256 pinned in
`contract.json` and not included.

The fixed 32-seed sample does not establish the population Poisson law,
parameter semantics, exact weights, stream independence, counts above five,
capacity shortage behavior above six formations, GUI visual content, or
cross-engine parity. The manual does not explicitly define `<POISSON>`
`PARAM1`; 1.5 is the intended mean and only the observed sample statistics
are claimed.
