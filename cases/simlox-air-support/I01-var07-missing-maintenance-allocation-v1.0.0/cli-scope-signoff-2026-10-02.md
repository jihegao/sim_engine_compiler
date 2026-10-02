# I01.var07 missing selected-category allocation — bounded negative CLI sign-off, 2026-10-02

**Decision:** Accept only the native converter rejection #2038 for a
task-referenced LRU-CM/BASE ItemRepair when the selected AIR_ALT POINT has
an ALT-CM allocation but no matching LRU-CM allocation. The rejected arm
has no valid simulation output; no repair, mission or inventory behavior is
claimed for it. Positive I01.var03 category, level and station selection
remains open. Keep Issue #18 open.

## Predeclared source and fresh execution

- Accepted I01.var01 stocked parent source SHA-256
  `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`.
  Matching source SHA-256
  `5201c389cccee418aec8aa8588e04e8b9f95ef7a77f4e8a633767f804a8a27fa`;
  other source SHA-256
  `c6d8c3ae578056a9236aa5e19c6889423a68670690cf327a5eaf86d863b58873`;
  exact diff SHA-256
  `a5b82da66d418462ea81b588923c7c5106b38cd71a6daec87dcd1e7b124b05c6`.
  The pair changes only APID AIR_BASIC→AIR_ALT and description. The new
  negative acceptance contract SHA-256 is
  `59ea984c9b70dd04f60b9746c85ef63150b7d92d6031da483e3cd8475493ae03`.
- Source input bytes, descriptions and exact diff were reused unchanged
  from an earlier unpublished I01.var03 diagnostic. Those descriptions
  still say I01.var03; that earlier contract treated rejection as a
  diagnostic and its run IDs are **not** acceptance evidence here. The new
  I01.var07 contract predeclared the exact negative gates before fresh runs.
  Independent pre-run static review approved that separate experiment.
- Both fresh session-0 SSH runs preserved GUI PID13340, used the host-wide
  mutex, completed import/export and exact 23-table roundtrip. The matching
  control had five steps, zero converter errors, valid SXO/report and 12 raw
  SHA-256 seals. AIR_ALT had four steps including roundtrip, exact error
  #2038, no report, and 9 raw seals. Authored replay passed 16/16 checks;
  independent read-only replay passed 1,084/1,084 with verdict
  `GO_BOUNDED_NEGATIVE_TASKCATEGORY_2038_ONLY`.

## Observed boundary and limit

The matching AIR_BASIC control includes an LRU-CM/BASE/BASE-01 allocation,
converts, and repairs failed LRU ID1 h10.1667–11.1667 after the h9.8829
failure; the repaired item returns to stock. Its 72-bin System and Stock
reports and terminal aircraft state reconcile. AIR_ALT selects only
ALT-CM/BASE/BASE-01 while ItemRepair still references LRU-CM. The converter
reports `Form: TaskCategory`, rec1 error #2038, `Errors: 1`, creates a
four-byte unusable SXO, and produces no simulation event log or JSON report.
Its calc process exit code is 0, so exit status alone cannot establish
success.

This is a negative selected-category completeness rule at one POINT,
station, item and seed. It does not establish generic missing POINT
behavior, positive category/level/station filtering, `<NONE>` reorder,
AIR_ALT physical-item disposition, GUI visual behavior or cross-engine
parity.
