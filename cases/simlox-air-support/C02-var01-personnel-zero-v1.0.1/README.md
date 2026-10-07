# C02.var01 personnel-zero v1.0.1 — corrected contract snapshot

This package is **contract only**. Its [contract](contract.json) corrects the frozen v1.0.0 ResultSummary gate by naming all eleven report fields and their expected values; three names begin with RSM, and RSSTMF is the fourth relative-variation field. The [v1.0.0 contract and independent NO_GO](../C02-var01-personnel-zero-v1.0.0/review/independent-contract-no-go-2026-10-07.md) remain unchanged and excluded from behavioral acceptance.

The proposed source is the accepted C02 single-step `single-both` input with only `ResourceAllocation` P-CREW `RQTY` 1→0 and `ProblemDescription.PDESC` updated. E-GSE capacity remains one and INSPECT still requests one unit of each resource. The new reserved run ID is `c02-var01-v101-personnel0-ssh-20261007-01`; neither this input nor a runner has been built. A native child requires fresh independent contract and exact prelaunch approvals.

The hypothesis is a failed typed crew request, available equipment, no partial booking or preparation work, no launch, cancellation by the authored latest-launch bound, and a ready aircraft at the 36-hour terminal. The exact cancellation instant must be observed in the new child. All 5,210 report cells require source/event reconciliation. The accepted equipment-zero and C01 crew-zero runs are context, not substituted C02.var01 results.

The [central publication index](../publication-index-v1.json) determines current publication status. This README records the prelaunch contract stage only; later findings belong in separate versioned evidence files.
