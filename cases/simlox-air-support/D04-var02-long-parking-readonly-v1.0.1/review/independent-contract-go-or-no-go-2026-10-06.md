# D04.var02 v1.0.1 independent read-only contract review

**Verdict: GO_CONTRACT_ONLY.** The corrected gate now distinguishes aircraft allocated to a mission (`NSYMA`) from aircraft flying (`NSYMO`) and matches every inspected accepted D04 boundary bin. A bounded catalog mapping can be made from the existing sealed run without a new native calculation. This verdict does not approve an author replay or publication.

## Frozen source and prior failure

- Reviewed v1.0.1 contract SHA-256 `5248f06f0d7500e449000e85d1ec59761fe6a404b63ee4e19fb48106814b9f59`. The preserved v1.0.0 contract SHA-256 `749fc1e2e8ec1dee16be5511597c3773f576f8fdec8d4f7a90bf85b28253a26e` and independent NO_GO `8c4b7c0abcd68b734388862a210344a039f24c22e37476fe090f183d49d5a4f1` match local bytes. That older ambiguous “mission0” gate remains excluded; it has no native run.
- Accepted D04 parent input `d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a`, signoff `44d668fa724b1cf63370c88a560e42d3f4e324071eee720a036d2905185fe831`, closure `3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45`, and all 12 raw SHA/size seals match. D03 prerequisite input/signoff, installed manual PDF and executable all match the contract's literal hashes. The catalog lists D04.var02 “long parking” as planned.

## Feasibility against sealed events and report

- Event log: physical aircraft ID0 completes its first mission at h10 and becomes ready, is allocated to the second mission at h39, flies h40–41, returns successfully h41, starts OP3 PM h41, completes it h42, and ends ready. There is no flight or PM strictly between h10 and h40; h39–40 contains mission allocation and preparation, not ready parking.
- The report has 120 contiguous half-hour SystemResults rows with 40 fields, 120 StockTotalResults rows with 16 fields, and one 11-field ResultSummary row. In all 58 h10–38.5 bins, `NSYRY=1`, `NSYA=1`, `NSYMA=NSYMO=NSYPM=NPMS=NPMT=0`. At both h39 and h39.5, `NSYRY=0`, `NSYA=1`, `NSYMA=1`, `NSYMO=NSYPM=NPMS=NPMT=0`. At h40 and h40.5, `NSYMA=NSYMO=NSYA=1`, with `NSYPM=0`. At h41 and h41.5, `NSYPM=1`, with `NPMS=1` only at h41; `NPMT=1` only at h42. The v1.0.1 contract now requires these exact distinctions.
- The default raw report contains a trailing comma, so preserving its raw hash and parsing only an in-memory normalized copy is the correct gate. The manual (physical p202 and pp370–375) grounds OPHOURS/PMINT interpretation, but neither raw report nor event log exposes the internal PM counter values. The proposed conclusion must remain an observation for one 30-hour no-flight gap and one fixed schedule; it cannot claim a general inactivity-accrual law or a second gap duration.

The next implementation review must independently verify all source/raw pins, event identity and full report ledger without importing an author checker, then separately audit any staged and remote publication. No native process or GUI was invoked for this contract review.
