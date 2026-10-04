# D15.var01 published verdict-byte repair — 2026-10-05

A read-only repository-wide check of 820 source entries in published evidence indexes found one Git-byte mismatch: this package's independent verdict. The original local verdict is 5,550 bytes with SHA-256 `3cc71e02f0882b7a0debdc29449da6f7f17b3cd8310e3d147d5e7a591a0a3666`, exactly as pinned by the existing evidence index. The previously published Git blob is 5,235 bytes with SHA-256 `a983110a50a06d0a72395d3fc5df9943b292ae24d8f8cd5729aa3a8e676ff68c`. The former becomes the latter solely by CRLF-to-LF conversion; parsed JSON and verdict content match.

The new `review/.gitattributes` disables text conversion for this one verdict. Restaging the original local file stores its indexed bytes in Git. The old LF blob remains in Git history. The package's indexed `.gitattributes`, existing evidence index, original pins, native inputs, runners and raw files are unchanged. The evidence-index file itself was already LF-normalized by Git, but it has no self-byte pin; its parsed content and all pins remain unchanged.

After staging, **20/20** indexed source entries match their staged Git blobs and local bytes. Both original run closures and invocations match, as do **124/124** raw SHA-256/size seals: 102 native and 22 selected-item-report artifacts. This repair adds no native call or behavioral claim.
