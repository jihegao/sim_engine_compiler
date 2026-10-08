# Captured object-order failure

The first formal local PURE capture stopped at the author `self_check.py` after `build.py` and `source_gate.py` exited 0. The author self-check exited 1 before the independent self-check ran. No SSH preflight or native child was started.

The original capture is `tmp/a17-var01-root-static-proofs-v100-20261008/20261008T170055527189Z-8a746bb1/receipt.json` (63,940 bytes, SHA-256 `7a2f54c190e96c86bc7484bb821d3a49923df5413fafe8c4caa6304f8f46f6e9`). Its original `2-stderr.bin` is 897 bytes, SHA-256 `212aeb15dd56f3542c702ccfae736af3e5f94977869afa308db0d42c78c880be`. The traceback points to the frozen `model_common.py` comparison requiring one JSON object member order. The original source is retained byte for byte as `model-common-v1-object-order.py.bytes` (4,581 bytes, SHA-256 `4170cdaa902ce4860a69bd7848aabe53949782347cf7c6d8d4d233953f62ce36`). The previous inventory method is retained as `inventory-v1-before-object-order.py.bytes` (5,558 bytes, SHA-256 `a74515ed3b66fa12944409b0c8b35e9b8ead7eacdda90025df6ab0bd2a245216`).

The repair compares JSON object field sets exactly while retaining table, instance, row, column, and cell order and typed values. This note records a failed original proof, not behavior acceptance.
