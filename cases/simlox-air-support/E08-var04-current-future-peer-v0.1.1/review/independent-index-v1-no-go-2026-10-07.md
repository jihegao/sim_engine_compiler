# First E08.var04 index — NO_GO_PUBLICATION_ARCHIVE_ATTRIBUTES

This decision binds the preserved first `evidence-index.json`, 189,754 bytes,
SHA-256 `d54410100e50d0ed0b1ca866fea79a4e2b9b91f0510a3542d32e7b305b095bb3`,
and its original `make_evidence_index.py`, 11,603 bytes,
SHA-256 `950299db9455db144d09ae4f2b9d8bf43ec96dccb6b87ebf2f677faf3c65c5e6`.
The separate read-only audit `independent-index-v1-no-go-audit.py`, 1,996 bytes,
SHA-256 `6f531d494357b04e963bc6819e50d06d3eab8b3849cead172894a466e4a98a39`,
rehashes all **118** original first-index source pins against disk with zero
local mismatch and identifies the 22 archived unpublished diagnostic files.

The archived v1.0.0 and v1.0.1 diagnostic trees each contain an active
`.gitattributes` (`* text eol=lf`). `git check-attr` confirms this overrides
the containing package's inert-byte setting for generic archived children.
Thus the first index did not establish an inert archive for staged Git-byte
publication. I do **not** claim an observed staged blob mismatch: no first
index stage was reviewed, and the archived PowerShell files with CRLF have
explicit `-text -eol` exceptions. The failure is an unsafe active metadata
policy for what should be byte-only historical evidence, not a native or
behavior failure.

Preserve the first index, builder, and all original/copy bytes as excluded
history. A separately named v2 index should point to byte-identical archived
copies whose `.gitattributes`/`.gitignore` names are inert, keep an explicit
original-to-old-copy-to-v2-copy SHA/size map, and receive fresh disk and
staged-Git byte audits. The corrected E08.var04 contract and the independent
48,684-cell `GO_BOUNDED` replay are unaffected by this publication decision.
