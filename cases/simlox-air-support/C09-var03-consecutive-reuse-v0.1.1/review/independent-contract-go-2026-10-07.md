# Independent C09.var03 v0.1.1 contract review — GO_CONTRACT_ONLY

- Frozen contract: `contract.json`, 39,399 bytes, SHA-256 `4200c13634a6f869250978861a4f64a47052e06c7184d391f2dacabbd542c297`.
- Decision: **GO_CONTRACT_ONLY** for a retrospective, read-only analysis of the three accepted C09.var04 native runs. This decision does not approve a checker, publication, or new native run.

## Independent checks

I compared the v0.1.1 JSON with the immutable v0.1.0 contract SHA-256 `0aa7c8269b95bf93795df830fa14bd50a5b25f6f9ecdf66db365fd524b970515` and its NO_GO memo SHA-256 `80c7e79e3412746652ed1d5d46ccaca7373dd618023fb3e6926a507ee875b273`. Both old byte identities match their new `excluded_v010` pins. The changed fields are schema/version, the excluded-version record, the event wording, and the report gates. Accepted parents, source matrix, raw run identities, native diagnostics, and bounded exclusions remain unchanged.

I independently checked 32/32 local source SHA/size records and the corresponding 32/32 published Git blob records: catalog, C09.var04 index/verdict and 17 source files, plus four each for C03, A17, and D01. All six accepted invocation pins and six closure pins match. The C09 three runs supply 36/36 raw seals, and the C03/A17/D01 prerequisites supply 11/12/12 respectively, for 71/71 raw seals. Installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` and dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` remain the cited native references. Manual physical pp. 399–400 and 414–416 distinguish immediate next-task use from return transport and conditional lender-shortage TTRSS.

The accepted remote log SHA-256 `28172e11ea223fa4387c6fbd7009407e78a62802e2f0ed4cfd21cfb338a99047` supports the revised gate: first P-MECH repair completes and deallocates quantity one at h9.28243, the second retests, receives, books and starts work at that printed timestamp, then the first task checks return. The revised contract calls this contiguous use **at printed time resolution with explicit release/rebooking**, and excludes continuous booking and named individual identity. It correctly separates failures at h8.28243/h8.46988 from repair requests at h8.53243, and does not infer a lender shortage from the backorder-removal line. C09.var04 already covers two sequential repairs; this variant can only add bounded event-order and ledger reconciliation.

The revised `all_cells` gate requires independently constructed expected values for all 5,210 cells in each of three six-table reports, rather than testing a native report against itself. Exact topology, IDs, strings, nulls, discrete counts and intervals are required; only time-weighted fractional fields may use justified field-specific bounds from printed event precision. The event-derived System, Stock and typed Resource ledgers, summaries, and totals are explicit acceptance obligations. Any unclassified non-null cell or report-only assumption must fail the later replay.

## Implementation boundary

The future read-only checker must actually visit and reconcile all 15,630 report cells, maintain separate typed P-CREW/P-MECH accounting, and prove BASE-02 lend → BASE-01 receive/book/release/rebook/release → return dispatch/receipt quantity conservation. It must preserve all old raw/source bytes and show the three control arms' differences without claiming a general scheduler rule, a persistent individual resource ID, TTRSS behavior, or a new native experiment. A separate exact-file review is required before any publication.
