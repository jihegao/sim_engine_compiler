# B01.var03 task-route contract review — 2026-10-06

**Decision: NO_GO_CONTRACT for current contract SHA-256 `0432b529385d20f26d93ca7d75545e8d2490050a94b61286334cd68a52385ca9`.** No native run or tracked-file edit was made.

## Verified design

The child source SHA-256 is `0cdb2bb68dcd49197988caba76b8d41e700b774139da98f33296c74c0d0d3c7b`; builder SHA-256 is `459a2a0bcbab69d4e7382186f57584d060d177b783db6ecf68f38b990fc01a98`. Comparing authored parent/child JSON finds one positional-cell change: `OperationProfile` row h8 `SPRID` changes `COLD-FIRST`→`HOT-SORTIE`. The h12 and h16 rows and all other model rows remain identical. Both mission types already have identical duration, aircraft requirement, notice, travel, and success parameters; their existing `MissionPreparation.TID` references select different linked preparations. No new recipe is authored.

The accepted B03 parent input SHA is `9c6b3c8955089b89caa1a71634eb78e9fd52069d5d710273e3a6bc710e19222c`, contract SHA `0d3d18196ce57dcbc8f36070ac53c532cdbaa313e0b9088eca8974af8a35127a`, and closure SHA `66bc79cf8609d89c5625299c7e61ede4f6f422e80af22e33bdbe166e18a6d96d`. All 11 closure raw SHA/size seals pass. The published A02 prerequisite signoff matches `608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e`. The installed manual SHA is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; physical pp294–297 explain mission preparation and linked task, and pp400–404 explain task types and breakdowns. Catalog B01.var03 is planned; no separate remote branch for this arm was found at selection.

## Blocking report gate

The contract requires the first hot preparation to finish at h7+1/6 and permits only `[7,7.5)` `NSYMP` 1→1/3 and `NSYMR` 0→2/3 to differ from the B03 `SystemResults` report. The accepted B03 report also records completion in `NPSUC`: row 14 `[7,7.5)` is **0**, while row 15 `[7.5,8)` is **1**. The proposed hot preparation completes inside row 14, so a faithful child must move that completion between bins. The frozen full-row equality gate would reject the anticipated native result.

**Recovery:** before native launch, freeze a corrected contract allowing exactly four System cells versus B03: row 14 `NSYMP` 1→1/3, `NSYMR` 0→2/3, `NPSUC` 0→1; row 15 `NPSUC` 1→0. Retain equality for all other 72×40 System cells, all 72×16 Stock cells, 11 summary fields and ProblemDescription. Retain the predeclared physical HOT-PREP h7–h7+1/6, h8/h12/h16 launches, three success/returns, source, converter and guard gates. Re-review the corrected contract and later exact runner/validator before any native call.

The bounded inference is an explicit MTID-to-recipe route on one fixed aircraft and station. It does not test history-driven cold/hot switching, different aircraft/site mapping, resources, faults, GUI visual behavior, or general B01.var03 semantics.
