# 阶段 C：批量并行与正式分段基准

状态：2026-09-20 已在 macOS arm64 完成。正式原始报告为 [macos-arm64-20260920.json](results/macos-arm64-20260920.json)，由 [run_benchmark.py](run_benchmark.py) 生成。

## 合同与验证

- 固定 F35 43 天 Execution Plan，fingerprint `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`，seeds `0,1,7`。
- 每个样本以输入位置作为 `sample_index`；重复 seed 合法，输出按 `sample_index` 稳定排序。
- `1` 与 `3` 线程的逐样本结果跨三次重复哈希一致。
- Python 绑定返回的三个 Rust 结果均与 Python reference 完整差分一致；比较范围包含随机请求、trace、指标与终态。
- 观测级别为完整结果。这里没有用 summary 模式或关闭 trace 来放大加速比。

## 正式结果

环境为 Apple arm64、10 个逻辑 CPU、Python 3.12.13、SimPy 4.1.1、Rust 1.90.0。每条路线预热 1 次，正式重复 3 次；下表均为中位数。

| 分段 | 中位耗时 | 对比 |
|---|---:|---:|
| Python reference，seed 0 执行 | 5.007 s | 1.00× |
| Rust，seed 0 单样本执行 | 3.060 s | 1.64× |
| Rust，3 样本/1 线程执行 | 9.047 s | 1.00× |
| Rust，3 样本/3 线程执行 | 5.762 s | 1.57× |
| Rust，3 样本/1 线程端到端 | 9.080 s | 1.00× |
| Rust，3 样本/3 线程端到端 | 7.493 s | 1.21× |
| Python 绑定，3 样本/1 线程调用 | 11.841 s | 1.00× |
| Python 绑定，3 样本/3 线程调用 | 7.228 s | 1.64× |

原生单线程中位分段还包括：Plan 读取 `0.968 ms`、解析/校验 `1.470 ms`、指纹 `1.239 ms`、RunState 初始化 `3.099 ms`、单样本序列化 `4.737 ms`、三样本批量序列化 `24.142 ms`、写盘 `5.673 ms`。完整批量 JSON 固定为 `13,347,502` bytes。

正式进程峰值 RSS 为 Python 基准进程约 `100.0 MB`，Rust 1 线程约 `261.0 MB`，Rust 3 线程约 `272.5 MB`。这些值是基准进程峰值，不是纯 RunState 增量：Rust 分段工具在同一进程中保留完整批量结果并重复构造端到端结果，因此不能把它解读为每样本内存，或据此宣称 Rust 已节省内存。

三线程没有达到线性加速。正式记录中的单线程批量为 `8.345/9.047/10.459 s`，三线程为 `6.617/5.760/5.762 s`；报告采用中位数，不采用更快的探测轮次。当前证据支持“独立样本并行有效”，不支持固定硬件上按线程数线性扩展的承诺。

## 复跑

```bash
uv pip install --python .venv/bin/python -e .
.venv/bin/python benchmarks/stage_c/run_benchmark.py \
  --output benchmarks/stage_c/results/macos-arm64-20260920.json \
  --seeds 0,1,7 --thread-counts 1,3 --warmups 1 --repeats 3
```

构建时间不计入报告。`run_benchmark.py` 会先构建 release 基准二进制，再分别计时 Python reference、Rust 原生和 Python 绑定；任何跨重复哈希、跨线程结果或 Python/Rust 差分失败都会使命令以非零状态退出。
