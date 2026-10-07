# Excluded transcript patch of mistaken draft

This is a transcription of the available `apply_patch` input that briefly created a reviewer draft at a mistyped `2026-09-09` path. The file was deleted before its bytes or SHA256 were measured. This artifact is **not** the original draft file, has no asserted original-file hash, and is excluded from contract acceptance. The false `NRW=3 at h0` claim was retracted in the formal NO_GO review.

```text
*** Begin Patch
*** Add File: C:\Users\user\Documents\Codex\2026-09-09\simlox-c04-deadline\repo\cases\simlox-air-support\C09-var02-lender-shortage-v1.0.0\review\independent-contract-no-go-2026-10-07.md
# Independent C09.var02 v1.0.0 contract review

Decision: **NO_GO_CONTRACT** for the frozen `contract.json`, 74,485 bytes, SHA256 `a5be822e37e784391ad1704f176cc3f7131f27b9c2615c5e9f24c74561a25f8c`. No child inputs, runner, or native runs existed at review time. Preserve this version and repair in a new contract version before construction.

## Evidence that supports the hypothesis

The installed manual SHA256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pp414–416, states remote support is for primary maintenance when outward transport is shorter than estimated local wait. Other immediately needing borrower tasks may use the quantity before its return. `TTRSS` is an optional return duration when the lender is short; it does not establish that a particular run will use that branch. The installed dictionary SHA256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` confirms the `ResourceRemoteSupport.TTRSS` floating-hour field.

The accepted C09.var04 remote run has one P-MECH at BASE-02 and a loan to BASE-01, but no lender-side demand. Its ordinary 0.5-hour return cannot demonstrate conditional `TTRSS`. The proposed paired HOME calendar-PM setup and TTRSS 0.5 versus 0.125 source contrast are therefore a falsifiable new test only if **both** arms physically show an overlapping lender request/shortage and an attributable return decision. The contract correctly avoids pinning old random failure times or a borrower trip order, requires complete 1,754-cell reports per arm, and distinguishes PM waiting from performing. The accepted D03 calendar PM, D12 PM subtask resource, and D02 IQTY-zero controls are separate mechanisms, not proof of their combination. An independent read-only pin traversal matched 78 source files on both local disk and published Git, 117 local raw files, nine closures, nine invocations, and 55 additional direct hash/size records; no mismatch was found. The accepted C09 remote authored/roundtrip topologies are both 32 tables, with 23 populated row tables and exact metadata for those populated tables, so the proposed 25 populated-table roundtrip gate is feasible.

## Defects requiring a new version

1. `common_source_delta_from_C09_remote` adds a Unit row with field `USTID`. The actual accepted `Unit` columns are `UNID, DESCR, STID, MAXPM, MAXPMP, NOTE`; `USTID` belongs to `Operations` and `SystemDeployment`. The proposed exact 32-table positional source gate cannot be built as written. Use `Unit.UNID = HOME-UNIT` and keep `Operations.USTID` and `SystemDeployment.USTID` as stated.
2. `predeclared_acceptance.report_semantics.cell_accounting` names `StockResultsTotal`. The accepted native report's exact six-table topology names `StockTotalResults`, with 16 fields. The arithmetic 1,754 cells per arm is otherwise sound; correct the exact table name rather than silently aliasing it after a run.
3. The `resource_pool` clause calls `NRN` a `Resource` source field, but accepted source `Resource` columns contain no `NRN`; `NRN` belongs to the `ResourceResults` report. It also labels `NRW` a maintenance-waiting quantity even though the accepted remote report's h0 row has `NRW=3` with no maintenance request. This wording cannot support the promised independent field-by-field resource ledger. Ground `NRN=3` in the two resource allocation quantities and label the report field explicitly; derive `NRW` from the observed resource-state intervals and accepted report semantics without equating it to a waiting maintenance task.

Recovery: freeze a v1.0.1 contract with these exact field and table corrections, pin this v1.0.0 contract and NO_GO memo as excluded history, and seek a new contract review. The positive physical-shortage and full-ledger gates should remain prospective. This review authorizes no native execution or acceptance of the combined behavior.
*** End Patch
```
