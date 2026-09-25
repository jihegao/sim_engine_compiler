# 整合基线：输入校验切片（优化前）

源码：`7b110db7f69e36048cfd95ac9d5182ffa9eea7cc`。这是 MC/O5/MLIR/cache-v3 整合后的新基线；后续三层 IR 与候选派遣改造必须另做对照。

Mac ARM64，4 个性能核、6 个能效核；OS 自行调度，未绑定核心或控制频率。32 样本使用 `0,1,7,7` 循环，三个重复；各次先预热一批，交替正反顺序。全部线程/重复/索引开关的逐样本 hash 在同一观测级别下相同。

| 路径 | 观测 | 线程 | 批量执行中位 ms | 样本/秒 |
|---|---|---:|---:|---:|
| baseline | full | 1 | 1488.61 | 21.50 |
| baseline | full | 2 | 944.07 | 33.90 |
| baseline | full | 4 | 595.88 | 53.70 |
| baseline | full | 8 | 375.10 | 85.31 |
| mlir-pass-on | full | 1 | 1727.23 | 18.53 |
| mlir-pass-on | full | 2 | 985.67 | 32.47 |
| mlir-pass-on | full | 4 | 604.77 | 52.91 |
| mlir-pass-on | full | 8 | 405.07 | 79.00 |
| baseline | summary | 1 | 1217.33 | 26.29 |
| baseline | summary | 2 | 762.84 | 41.95 |
| baseline | summary | 4 | 441.79 | 72.43 |
| baseline | summary | 8 | 302.23 | 105.88 |
| mlir-pass-on | summary | 1 | 1469.58 | 21.77 |
| mlir-pass-on | summary | 2 | 842.97 | 37.96 |
| mlir-pass-on | summary | 4 | 553.13 | 57.85 |
| mlir-pass-on | summary | 8 | 360.54 | 88.75 |

`batch_execution` 包含 prepared layout、RunState 初始化、线程池及执行；读取/验证/序列化/写盘另列在 `batch.json`。进程峰值 RSS 包含预热，不是单轨迹内存。八线程涉及异构核心，不能据此宣称同构核的线性扩展。

| 三组对照的时间 profile | 无索引总成本 s | 索引总成本 s | 总成本变化 | Guard 减少 |
|---|---:|---:|---:|---:|
| legacy-minute-v1 | 2.0491 | 1.8874 | -7.89% | 95.95% |
| event-time-v2 | 0.5061 | 0.6567 | +29.74% | 14.24% |

总成本口径沿用三组对照工具：一次编译、一次加载/验证，以及 seeds 0/1/7 各三次 full 运行的 profiled 初始化+执行；不含序列化/写盘。编译各预热一次并重复三次，运行臂交替顺序；运行无独立丢弃预热。索引开/关 full RunResult 完全一致。O5 叠加索引的成本上升；本轮不推广索引为默认，也不将其历史收益与 O5 相加。

AOT v3 canonical 缓存：Python lowering 中位 10.121 ms；Rust miss 进程墙钟 25.921 ms、hit 10.202 ms；包含 O5 summary 执行时，miss 59.755 ms、hit 51.825 ms。仅三次重复，是本机当前版本基线；不包含 Project exporter/Adapter，也不是 pre-Adapter Project-cache 或 Rust Adapter 迁移。各分段原始纳秒值见 `cache-v3.json`。

验收：Python/Rust 共享 34 个输入用例×两个 profile，五个已保存 Plan 精确一致；12 个 Rust compiler 与 32 个 runtime/benchmark 测试通过；六个强制 MLIR 测试零跳过。本机完整 Python 运行的其余 51 个测试通过，只有 PyO3 类初始化遇到既有 macOS LINKEDIT 加载器错误，不能称本机全套通过。Linux 绑定与 CI 证据单独保存。

当前局限：单主机计时、未量化分配次数、未控制后台负载；未测 NUMA、第二真实资源网络和 Project 冷启动。CPU load 记录在 `identity.json`。此切片不代表 #4 三层 IR 或 #6 候选派遣已完成。

补充验收：Linux CI [36140553553](https://github.com/jihegao/sim_engine_compiler/actions/runs/36140553553) 在该源码提交上全部通过，包括 PyO3、Rust AOT、完整 Python suite 和六个强制 MLIR 测试。AMD128 同一引擎源码的 9 个绑定测试也通过；其 32 样本 summary MC 热缓存调用在 1/2/4/8 线程分别为 3399.46/2131.42/1596.85/1308.67 ms（含 Python 输入编码、引擎和结果返回），完整结果逐样本一致。独立 Linux/工具链/扩展 SHA 与原始记录在 `../amd128-binding-20260925.json`，不可与本页 Mac CLI 数值直接相除。命令：`PYTHONPATH=src .venv/bin/python benchmarks/integrated/run_binding_benchmark.py --source-commit 7b110db7f69e36048cfd95ac9d5182ffa9eea7cc --output /tmp/sim-strict-linux-binding-baseline.json`。
