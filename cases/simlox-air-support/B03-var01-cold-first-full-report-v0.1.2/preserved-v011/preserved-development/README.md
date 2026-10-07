# Author development diagnostics

These are local, read-only replay development failures. No SIMLOX child was started and no accepted raw byte was edited.

- `replay-draft-01.py` (21,085 bytes, SHA-256 `bb24191ee274889dc614cdf0802f971df2f0698891e0dc52f69730e171a48c87`) searched for a main task with substring matching. Three lines matched because two subtasks say `within system preparation task 0`. Its empty stdout is SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; stderr is 1,309 bytes, SHA-256 `257674be1d34bf19272323ab51a666ead944bf16f759c68d99065962b02c9b36`.
- `replay-draft-02.py` (21,204 bytes, SHA-256 `8d699b6e204fb93fe099a29d63d4a2d43665fd0c5ecc652a11cc04914672924d`) fixed the main task predicate but matched all three physical return lines across waves when one return was requested. Its empty stdout has the same empty SHA-256; stderr is 1,278 bytes, SHA-256 `7d0a1d8d36b62e6b9566af36a8b65febdfbfae85c09949c57752bab83ff97cc9`.

The corrected reader binds the main task to a complete typed line and the return to the expected mission time and causal event order. It also rejects extra main task and return records globally. These historical failures did not change the frozen v0.1.1 contract or the accepted B03 runs.
