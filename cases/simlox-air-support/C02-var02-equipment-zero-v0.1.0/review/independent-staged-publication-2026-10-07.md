# C02.var02 staged publication review — 2026-10-07

**Decision: GO_STAGED** for the bounded, retrospective equipment-zero classification. This memo is untracked and outside the frozen evidence index.

- Exactly 13 intended paths are staged: 12 files under `C02-var02-equipment-zero-v0.1.0` and the root `publication-index-v1.json`. No native run blob, product code or unrelated path is staged. `git -c core.whitespace=cr-at-eol diff --cached --check` passes.
- Evidence index SHA-256 `23e5eb761628e228f204240ac67f251de998ca225cabc74161aa813e91940c9d` has 11 new source records; each SHA/size matches both disk bytes and staged Git bytes. The indexed contract, author and independent review, README and signoff links resolve.
- All 18 accepted C02 source identities match local and published `origin/simlox/main` bytes. The intentional `.gitignore` exception is separately sealed: local CRLF eight-byte SHA-256 `8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f`, published Git LF seven-byte SHA-256 `127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933`.
- Final original `serial-both` and `serial-equipment-zero` closure SHA-256 values `86c0de86b8494953d39704aafe64f6aab7038e2a649d684a926739b399670c84` and `79ab8014a50ed3797a537d8395c9ba1a60b97eb27be26b187e5c93860bbe6d64` match, as do both invocations and all 22 local raw SHA/size seals. The two authored inputs differ only at the E-GSE `ResourceAllocation.RQTY` cell 1→0; crew capacity remains one and other cells match.
- The author verdict is 53/53 and the independent verdict is 11,252/11,252, including all 5,210 cells of each six-table report. Signoff confines the conclusion to one fixed-seed joint-resource task and the observed no-partial-booking/cancellation contrast; it does not assert a general resource allocation or deadline rule, a new native run, GUI evidence, or full Issue #18 completion.
- The root index preserves all 470 prior entries and non-entry metadata, then adds one unique bounded 471st entry `C02.var02.equipment_zero.0.1.0`.

This staged verdict does not establish remote PR bytes, CI success or broader engine behavior.
