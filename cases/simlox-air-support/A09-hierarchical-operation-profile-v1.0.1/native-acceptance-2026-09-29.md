# A09 v1.0.1 native CLI acceptance — 2026-09-29

**Result:** the `nested-v101` candidate passed one isolated, source-bound
SIMLOX CLI run on `4700-3`. This is native CLI behavior evidence for the A09
four-wave, 48-hour contract. GUI model review and publication remain pending.
The pre-run [contract](contract.json) is frozen; this record does not alter it.
This record was written and the README was updated after the run; the bundle manifest
binds the model, builder, runner, validator, contract, and shared parser bytes
that were actually executed.

## Source and run identity

| Item | Recorded value |
| --- | --- |
| Source bundle | `C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\bundle.zip` |
| Bundle SHA-256 | `ed46e1c02e642996db41ed5bb608522a9ce19f071d3b3761c58f7446f02783ac` |
| Run ID | `a09-v101-20260929-01` |
| Run directory | `C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\repo\cases\simlox-air-support\A09-hierarchical-operation-profile-v1.0.1\runs\a09-v101-20260929-01` |
| `input.json` SHA-256 | `e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85` |
| `invocation.json` SHA-256 | `7188ce95ef841c5b4c13a132a1ac93ee947239db002b227e21af4202a87a1892` |
| `closure.json` SHA-256 | `8f09c55a929286d55fd872d9e635be98aa8289bb61ecf25e1eb20e608cded942` |
| `validation.json` SHA-256 | `0ca9a23128e1b52f88682c09ff841df7cf8114f6c02e31a6bea288030b83aba8` |
| `model.log` SHA-256 | `c87d12ebe855b1a4c6e987318b2ea247ced02d76b25d676d707b6c42588b9ba6` |
| `report-raw.json` SHA-256 | `36cd362bb15e70e388c77885143a359a6d78a4204aa63bbcabf29943c0d618b6` |

The SSH runner used session 0 with `-AllowExistingGui`. Its invocation bound
the existing interactive SIMLOX process to PID `13340`, session `1`; the
import, export, calculation, and JSON report steps each exited `0`, passed
the GUI-state check, and recorded that the same GUI remained present. CLI
coexistence does **not** count as GUI model review.

## Native result and independent read-only replay

The retained `validation.json` reports `passed=true`, `differences=[]`, a
business-row-equal native roundtrip, and four distinct native mission tags.
An independent read-only fetch of the remote raw files confirmed:

| Observation | Native result |
| --- | --- |
| Mission notifications | 7, 19, 31, 43 hours |
| Mission starts | 8, 20, 32, 44 hours |
| Mission completions | 10, 22, 34, 46 hours |
| Cancellations | 0 |
| `ready` / `systems_ready` / `soon_ready` events | 8 / 5 / 4 |
| `SystemResults` half-hour intervals | 96 |

The new `model.log` and `report-raw.json` each match the passed v1.0.0 flat
control **byte for byte**. Their SHA-256 values above equal the flat raw
files' hashes. The native validator checks the four complete lifecycles,
readiness event identities and times, all observed `ResultSummary` fields,
and the 96 interval-level `SystemResults` profiles, including `STACC`.

The observed four waves support this particular `IPER=48`, `IQTY=2` nested
input under the pinned native executable and contract. A single successful
candidate does not establish a general `IPER/IQTY` expansion formula or
validate other quantities, periods, profiles, or engines. GUI review is
**not_run**; publication is **not_published**. Full A09 method coverage and
cross-engine equivalence remain unverified.
