# Issue #18 source review

Review date: 2026-09-27 (Asia/Shanghai)

## Scope

This review covers the frozen resource-behavior validator and its local tests. It is
separate from native execution, GUI review, cross-engine equivalence, catalogue
promotion, and dependency-chain acceptance.

The earlier `initial-probe-review.md` records the historical `b26313f353ab`
snapshot. Its C01--C03 conversion failures and B03 contract-hash warning describe
that old snapshot and are retained as immutable history; they do not describe the
current `f8b2face730d` probe inputs or this source candidate.

## Reviewed source

- `validate_resources.py`: `bf12e5a187f2a702e9e541f547cf5b11ea8adbbcaef1a9eec428ceab1efd4664`
- `test_simlox_resource_behavior.py`: `b4ab496313b5fbbc9e1d34dc532673cc0baeb8b02c40591fb499a4f768e2b8a8`

The validator keeps resource behavior in a dedicated parser. It binds owner and
subtask identities to ordered request, availability, booking, allocation, work,
completion, free, release, and preparation-end evidence. Blocked paths reject
partial leases and work, and require the observed cancellation and stopped-wait
sequence. Resource report values are checked per interval and do not substitute
for the ENLOG lifecycle.

## Independent checks

- 91 targeted conformance tests passed using
  `/tmp/simlox-issue18/test-venv/bin/python -m pytest`.
- `generate.py --check` passed for all 12 candidates. Every generated candidate
  remains `native_verified: false` at this source-review gate.
- The resource validator replayed all nine retained `f8b2face730d` C01--C03 raw
  probes successfully.
- A separate 16-mutation matrix rejected wrong owner, availability outcome,
  request quantity, booking, grant resource, grant balance, work start,
  completion, free, release resource, release balance, preparation end, launch,
  mission completion, and duplicate-grant evidence. The legal C03 exchange of
  the two symmetric aircraft owners still passed.
- Earlier focused mutations also confirmed rejection of decreasing timestamps,
  release-before-next-step violations, retry-before-release violations, a
  resource-received event placed after work start, injected work or leases on
  blocked paths, missing availability continuation detail, wrong report interval,
  and forged mission summary values.

## Source-review conclusion

The resource validator source above is approved for binding into the final native
snapshot. This approval is limited to the fixed C01--C03 contracts and retained
CLI evidence shape. C03 staffing-0 accepts the observed cancellation at minute
510 for this fixed profile; it does not verify the general C04 cancellation rule.

No native run is approved by this document. A run may receive the limited
`isolated_contract_cli` result only after the final validator, binding code,
contract, candidate input, invocation, closure, and raw artifacts are sealed and
their hashes are independently reproduced. Publication stays `not_published`,
and unmet parent-case prerequisites prevent catalogue promotion or dependency
closure.
