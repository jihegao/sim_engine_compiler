# Excluded first index draft

The first dry index command exited before any index write because its new builder expected an LF after the frozen seven-byte `.gitattributes` value `* -text`. The source bytes (SHA256 `452ff9c95baa7b4afded4fb19686b3960cbb8b90ad9d009976552867add61b81`) are preserved here. The failure stderr was visible only in the tool transcript; no original stderr byte file was captured. The corrected builder compares the actual frozen seven bytes. No source, run or catalog bytes were changed by the failed dry command.

The second dry command exited after all behavior and custody checks because the closed source inventory had not yet named this development note and draft. Its exact builder source SHA256 `f2575921f13a7e80bc0f67e8f4e0258988fcf4b4ca7efd8b3bc3a2b76ca59e9c` is also preserved. Its failure stderr was tool transcript only. The final builder includes both excluded drafts and this note in its fixed source set.

The first postrun reproduction guide was preserved at 2,180 bytes/SHA256 `a99e1be8c567013b413bf6f74a4f6205d92b12dd56c9d383b292c0c6fdef015b` before adding a fresh-derived-work procedure. That earlier guide was a draft, not a second native run instruction.
