# Independent v3 static decision: GO_STATIC_ONLY

The v3 method is ready to be pinned as the independent read-only reviewer method in a fresh manifest. It does **not** authorize an SSH case preflight or native run. The frozen v1 and v2 methods remain NO_GO; their defects and root receipts are preserved in separate dated memos.

Exact reviewer files (bytes, SHA-256):

- `independent_replay_v3.py`: 58,981; `e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e`
- `independent_self_check_v3.py`: 21,326; `46b09155540c59de9369b26f4f6258d4c079e6cb75710dbd841bd075a35d73ae`
- `independent-static-verdict-v3.json`: 173; `0ee96baf97949684e03cdc157120f11bda0c305efeee25f2e2ab4653827a9c8f`
- `independent-self-check-verdict-v3.json`: 2,505; `7ae32c09629f1a7198bcccc38efe5f32dff744843ca8f6135f208063af65bd97`

The independent static run checks all 5,210 accepted parent report cells and predicts all 5,210 child cells from frozen source and typed intervals. The separate synthetic child fixture passes 5,210 report cells and 58 in-memory rejection probes, including the earlier three continuation/resource/ready escapes, two same-time return-order escapes, all five ResourceTotal means at plus and minus one binary32 ULP, and task-bound remote-return diagnostics. Root's separate 40-mutation probe rejected every mutation against these exact v3 files: `tmp/probe-i03-var02-independent-v3-final-20261007.py` 3,959 bytes, SHA `10fe9e9d17a813c602581a463a84c3668d84cc8b53a9234ec7424789ffb9bf88`; receipt `tmp/i03-var02-independent-v3-final-probes-20261007.json` 10,434 bytes, SHA `09fdab95afd1b53a2d728c1cfd9173f68ea24d42923a407b3e32773702985cd4`.

As a fixture compatibility check, the author-generated synthetic log passed the independent physical gate (1,628 checks), and the independent synthetic log passed the author's separate typed event gate. The independent acceptance code does not import the author implementation. Neither fixture is native evidence. The child run is absent at this decision; prospective native and report acceptance remain separate gates. The accepted parent's historical child PID/session capture remains unverified by this static review.
