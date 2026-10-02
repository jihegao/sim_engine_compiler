# H01.var01 DAMP endpoint CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded native `DAMP=0/1` contrast with a certain attrition consequence after author and independent replay. Publish only this observed `H01.var01` slice; Issue #18 and the wider H01 checklist remain open.

## Frozen model

- Accepted A02 parent source SHA-256 `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
- Zero input SHA-256 `5c5b26aae958c4fa610d05f2cc82445bfb0fb13159dc4e6b5dace2375be2f638`, native run `h01-zero-v100-ssh-20261002-01`.
- Certain input SHA-256 `f519cd4549db879505c16bd5d4affb7e34f1db6227e71bebc27738442489d4f0`, native run `h01-certain-v100-ssh-20261002-01`.
- Exact diff SHA-256 `3b3266332d74c9bf230dd5e09d1ff2b37d7828eff438c4681f31b7e6732e22f4`: A02→zero adds DamageType/MissionDamage/DamageItem plus PDESC; zero→certain changes only MissionDamage.DAMP 0→1 and PDESC.

## Native observations and reconciliation

Both arms completed five guarded session-0 SSH steps with the host mutex and GUI PID13340 preserved. Each exactly roundtripped 16 authored row tables and converted with Errors: 0. Warnings #108 and #126 are respectively the enabled simulation log and inherited no-item generic aircraft.

The control logs three starts h8/20/32 and three successes/completions h10/22/34; no damage or attrition. The certain arm logs one `BATTLE-LOSS` damage and `<ATTRITION>` consequence h8.78145 during the first mission, an abort at that instant, and aborted completion h9.28145. Its later scheduled missions cancel at h20.3333 and h32.3333, with no later start or success. These event identities, rather than aggregate summary fields alone, establish the bounded outcome.

Each arm has 72 aligned half-hour System and Stock bins. The control integrates 6 aircraft-hours of operation, 0 lost-aircraft hours and terminal ready1/lost0. The certain arm integrates 0.78145 operating hours and 27.21855 lost hours from the damage to horizon36, with terminal ready0/lost1. All Stock cells match between arms, including `PNB=1` in both; aircraft attrition does not establish a stock decline. `ResultSummary.MSTF` is 1 in control and about one-third in the attrition arm, while `MSUF` is 1 versus 0; these values are reported as native metrics, not substituted for the explicit mission events.

## Limits

The manual describes DAMP as per-mission probability, with occurrence time drawn within the mission. This one seed and `DAMP=1` show occurrence and timing in a single first mission; later missions cannot test repeat-per-mission behavior because the only aircraft is permanently lost. Intermediate DAMP, `DAMRT`, alternate consequences, repairs, continuous missions, multiple aircraft, GUI-only behavior and cross-engine parity remain unverified. The author replay passed 28/28 checks and the independent read-only replay passed 7667/7667; their verdicts and SHA-sealed raw files are bound by `evidence-index.json`.
