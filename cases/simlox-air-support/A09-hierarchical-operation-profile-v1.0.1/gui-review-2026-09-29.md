# A09 v1.0.1 partial GUI review — 2026-09-29

Status: **partial GUI observation; `not_published`**. This record supplements the [native CLI acceptance](native-acceptance-2026-09-29.md). It does not change the frozen [contract](contract.json), source/run files, or case catalog status.

## Identity and evidence

The existing SIMLOX 2017.2 GUI on `4700-3` (PID `13340`, Windows session `1`) stayed running. The reviewer opened `C:\Users\user\Downloads\A09-v101-20260929-01.sxi` and `.sxo` in that GUI. These are renamed, hash-identical copies of the native run's `model.sxi` and `model.sxo`, not the files at their original run paths. The SXI SHA-256 was `941086de17e0800cf34cffadfe45e938c0df9a585421ee2f5d5e4a18432a97df`; the SXO SHA-256 was `8b825f5ef87c4a212dcd34bfe4b7021631dc50ffa180cb5a67741c5462740b93`. The result selector displayed `A09-v101-20260929-01`, matching the CLI run ID. File identity was confirmed by SSH hashes as well as the GUI opening actions; the screenshots alone do not display full paths or hashes.

Original evidence directory on `4700-3`: `C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\repo\cases\simlox-air-support\A09-hierarchical-operation-profile-v1.0.1\runs\a09-v101-20260929-01\gui-review`. The two PNGs below were copied there from the RDP session's Snipping Tool output and their hashes were checked against the saved originals.

| GUI screenshot | Bytes | SHA-256 |
| --- | ---: | --- |
| `a09-v101-operation-profile-gui-20260929.png` | 95,942 | `2121d3e6f8df69386bfb0294c8c5a3b469fd664f35826e8a5859df1a00277bf9` |
| `a09-v101-fixed-mission-quantity-gui-20260929.png` | 344,128 | `4329ad57ad129e2c05966c52ae330db1d1a194f42d837315917a790089055e11` |

## Direct GUI observations

- The `OperationProfile` table displayed the parent row `BASIC-SCHEDULE → A09-DAILY-TWO-WAVE` with `STIM=0`, `ITYPE=SCHEDULED`, `IQTY=2`, and `IPER=48 h`. It displayed two child rows `A09-DAILY-TWO-WAVE → BASIC-MISSION`, at relative `STIM=8 h` and `20 h`, each with `IQTY=1`, `IPER=0`, and `DTIM=0.3 h`. This is a check of the model data visible in the native GUI, not a proof of the general `IPER/IQTY` expansion rule.
- The result view displayed `System Results > System Availability = 1.00`. Under `Mission Results > System Time`, the accumulated curve reached 8 aircraft-hours in four 2-hour steps. Under `Mission Results > Fixed Mission Quantity`, with `Accumulate` checked and `TEACH-UNIT` / `BASIC-MISSION` selected, the `Successful` series reached 1, 2, 3, 4 around 8, 20, 32, 44 hours. The saved mission-quantity screenshot captures the selector, series and four steps; the other two charts were observed in the same GUI session but not separately saved.
- The GUI read of the hash-identical SXO copy is consistent with the CLI's four completed missions. Exact notification, start and completion times, cancellations, and 96 half-hour `SystemResults` intervals are established by the retained CLI files and strict validator, not by these charts.

Full GUI review of remaining A09 input tables and detailed result tables is pending. A01/A02 parent publication gates are pending. No full A09 method coverage, general nested-profile formula, cross-engine equivalence, or reusable publication is claimed. The GUI process was left running.
