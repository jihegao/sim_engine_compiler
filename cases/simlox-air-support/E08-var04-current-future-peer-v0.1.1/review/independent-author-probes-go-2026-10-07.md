# Independent review of author semantic probes — GO_PROBES_ONLY

I read and ran `self_check_v2.py`, 11,137 bytes, SHA-256
`7b991e0d76cde281930303d1693dda6597f753d8a9cfd13c050a72e8c225179c`.
Its read-only output parsed equal to saved `author-self-check-v2.json`, 1,011 bytes,
SHA-256 `73a8648277530a8c36419a56d6cbf4e124680818fade0cbdd3f4981e553c8bf7`.
The baseline independently invokes the author's production replay and covers
48,684 cells, then **24 distinct in-memory mutations reject** through the
production source, physical, report, or pin gates.

The added mutations close the previously observed test coverage gap:
fractional System, Item, and Stock cells above their calculated edge bounds;
current and future receipt/backorder line inversion; fit-work/completion
inversion; a future lateral selection; and mismatched raw model log, closure,
invocation, and station-selector seals. The source stock-delta, physical ID,
route, quantity, report metadata, integer, null and bounded no-wait presentation
probes also reject. The pin probes change only in-memory expected SHA values
and restore them; accepted source/raw bytes are unchanged.

The original author `replay.py` SHA-256
`9cc22516d1fbd9fdee1f0b8c2e09980f57bfccba8e0421b00c492777c8b56ad7`
and original `self_check.py` SHA-256
`8c3e6a93e87e57363845678d59e0b3d84aa2551049a6c9e1968aaaaf3fe22ff6`
remain byte-identical. This memo approves the coverage of the frozen contract's
negative probes, not the later publication index, staged Git bytes, or a new
native run. The separate reviewer qualification
`independent-presentation-qualification-2026-10-07.md` SHA-256
`60da09c21aa8b052b84f9ad92a54c176c5a4e44bf88e66a55dd3f5d74e3dbb14`
limits WTS=null with no positive wait to this bounded native presentation.
