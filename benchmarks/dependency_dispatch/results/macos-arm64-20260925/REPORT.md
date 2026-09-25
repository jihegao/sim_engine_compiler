# 三层 IR 与候选派遣：验收与采用决定

源码固定为 `49b226dd4b78267c87f52ebdaedbe258faff1951`；旧编译链对照为 `7b110db7f69e36048cfd95ac9d5182ffa9eea7cc`。运行环境为 macOS 27 arm64、Rust 1.90.0、Python 3.12.13、LLVM/MLIR 23.1.1。4 个性能核加 6 个效率核；OS 自行调度，未固定频率或 affinity，后台负载见 identity。以下是指定环境的实测，不是跨机器保证。

**决定：三层 IR 主链完成；候选派遣作为显式 opt-in 实验保留，不提升为默认。** F35 minute 的访问工作量下降，但相对已有缓存扫描的端到端收益很小；O5 与集中资源竞争场景未达到默认采用门槛。编译链本身有明确成本增加。

## 语义证据

- Python/Rust 正式 canonical 入口都先生成 Business、symbolic Core，再 layout 出独立 Plan。五个固定输入 × 两个 profile 的两个中间层全树一致；原合法输入 Plan 与旧编译器一致。
- 独立文件重载、Business/Core 规则编辑、符号重定位、非法 operation/依赖/引用/单位/字段类型拒绝均有可执行测试。B1 与 F35 的产物、规则修改及 impact map 位于 `../compile-20260925`。
- 三组派遣完整结果逐树相等，覆盖 F35 seeds 0/1/7 × minute/O5 × Full/Summary；B1/B2/B3、16 架资源竞争/缺货/远端人员设备运输、到达与取消边界。随机请求 tape、trace、metrics、终态均在完整结果内。重复 seed 和 1/3/4 线程输出顺序也已验证。
- MLIR 接受 Rust AOT 保存的 Core，和 Python 输入路径生成相同索引 Plan；重新封印的缺失远端容量依赖仍被拒绝。候选模式拒绝 v1/无索引。
- 本机全套在 `75176c8` 执行 65 个测试；随后 `49b226d` 的畸形 Core 补测通过。全套唯一错误为已知 macOS PyO3 LINKEDIT 加载失败；不是零错误通过。两个 Rust crate 的测试通过，Linux 必需 MLIR 与绑定验收另行记录。

## 编译成本（7 次中位数，ms）

Python 是已加载 canonical 字典到 Plan 的进程内时间；Rust 是包含输入读取、编译、二进制缓存封装与 JSON Plan 写盘的 CLI 整体时间。两列边界不同，不能直接用来宣称语言加速比。旧/新 Plan 完整一致。Rust 次序交替；Python 旧/新分别预热测量。工具构建时间排除。

| 输入 | Python 旧链 | Python 三层 | Rust CLI 旧链 | Rust CLI 三层 |
|---|---:|---:|---:|---:|
| b1 | 0.068 | 1.574 | 3.467 | 4.619 |
| f35 | 8.600 | 80.267 | 15.501 | 47.485 |

F35 新链独立分段中位数：canonical_to_business 14.40 ms, business_to_core 29.29 ms, core_to_plan 37.06 ms, business_read_parse_validate 14.13 ms, core_read_parse_validate 10.18 ms。这些独立微基准不要求相加精确等于整条链。成本来自物化、复制、重复验证与指纹；本轮未做未经差分的快速旁路。

## 派遣端到端（未插桩 CLI，ms）

每组先逐树比较 seeds 0/1/7，再每臂预热一次；3 次重复按轮换 arm 顺序执行，总计每臂 9 个样本。表为这 9 次进程 wall 的中位数，含启动、加载/校验、初始化、执行和 pretty JSON 写盘；不含一次性编译。profile 由独立运行采集，不混入此时间。

| 案例 | profile | 观测 | 无索引扫描 | v2 缓存扫描 | v2 候选 |
|---|---|---|---:|---:|---:|
| f35 | legacy-minute-v1 | full | 188.23 | 172.14 | 173.19 |
| f35 | legacy-minute-v1 | summary | 167.54 | 154.00 | 148.33 |
| f35 | event-time-v2 | full | 65.68 | 78.13 | 83.59 |
| f35 | event-time-v2 | summary | 46.51 | 60.29 | 63.16 |
| synthetic-capacity-16 | legacy-minute-v1 | full | 3.77 | 3.94 | 3.96 |
| synthetic-capacity-16 | legacy-minute-v1 | summary | 2.93 | 3.20 | 3.19 |
| synthetic-capacity-16 | event-time-v2 | full | 3.81 | 3.89 | 3.91 |
| synthetic-capacity-16 | event-time-v2 | summary | 2.99 | 3.25 | 3.09 |
| synthetic-shortage-16 | legacy-minute-v1 | full | 3.31 | 3.25 | 3.23 |
| synthetic-shortage-16 | legacy-minute-v1 | summary | 2.90 | 3.23 | 3.10 |
| synthetic-shortage-16 | event-time-v2 | full | 3.16 | 3.28 | 3.32 |
| synthetic-shortage-16 | event-time-v2 | summary | 2.86 | 3.18 | 3.05 |
| synthetic-remote-16 | legacy-minute-v1 | full | 3.95 | 4.24 | 4.23 |
| synthetic-remote-16 | legacy-minute-v1 | summary | 3.11 | 3.22 | 3.32 |
| synthetic-remote-16 | event-time-v2 | full | 3.93 | 4.28 | 4.27 |
| synthetic-remote-16 | event-time-v2 | summary | 3.04 | 3.32 | 3.21 |

三个 synthetic 案例均由 B1 明确扩大为 16 架，不作为第二个真实上游案例。毫秒级小样本受启动和调度噪声影响，不依据微小差值宣称稳定收益。

## 访问量与维护工作

下表统计独立 profile 中 seeds 0/1/7 的总和。候选总访问 = 实际候选 + 延迟事件重放；只看 guard 减少会夸大收益。

| 案例/profile/观测 | 原扫描访问 | 缓存 guard | 候选访问 | 候选重放 | 候选 guard | 失效通知 | 队列构建/合并 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| f35/legacy-minute-v1/full | 335027 | 13579 | 14312 | 0 | 14312 | 83341 | 5.595 |
| f35/event-time-v2/full | 15833 | 13579 | 13790 | 0 | 13790 | 83341 | 1.710 |
| synthetic-capacity-16/legacy-minute-v1/full | 1266 | 1266 | 486 | 780 | 486 | 1968 | 0.110 |
| synthetic-capacity-16/legacy-minute-v1/summary | 1266 | 1266 | 486 | 0 | 486 | 1968 | 0.064 |
| synthetic-capacity-16/event-time-v2/full | 1266 | 1266 | 486 | 780 | 486 | 1968 | 0.110 |
| synthetic-capacity-16/event-time-v2/summary | 1266 | 1266 | 486 | 0 | 486 | 1968 | 0.060 |
| synthetic-shortage-16/legacy-minute-v1/full | 1536 | 96 | 96 | 0 | 96 | 96 | 0.009 |
| synthetic-shortage-16/event-time-v2/full | 288 | 96 | 96 | 0 | 96 | 96 | 0.006 |
| synthetic-remote-16/legacy-minute-v1/full | 1248 | 1248 | 366 | 864 | 366 | 2508 | 0.125 |
| synthetic-remote-16/event-time-v2/full | 1248 | 1248 | 366 | 864 | 366 | 2508 | 0.120 |

`queue_ns` 只覆盖队列构建/排序及阶段内失效合并；`queue_updates` 只计失效通知。其余动态索引维护包含在完整 phase 和未插桩 wall 中，不能把这些局部计数当作全部维护成本。Full 容量竞争的 486 次候选加 780 次重放仍等于原来的 1266 次访问；Summary 才可省掉重放。F35 minute 335027 → 14312 次访问（减少 95.73%）并不等于端到端加速 95.73%。

## O5 小批量（8 个样本，ms）

固定 seeds `[0,1,7,7,0,1,7,7]`，每配置一次预热、3 次重复；表为包含 Plan 读入/校验、执行、序列化与写盘的中位数。每个观测级别跨 arm 和线程的 samples SHA-256 全部一致。完整分段在对应 batch JSON。

| 观测 | arm | 线程 | 批量端到端 ms |
|---|---|---:|---:|
| full | scan | 1 | 415.84 |
| full | scan | 4 | 185.51 |
| full | cache | 1 | 496.65 |
| full | cache | 4 | 196.39 |
| full | candidates | 1 | 506.33 |
| full | candidates | 4 | 204.36 |
| summary | scan | 1 | 317.62 |
| summary | scan | 4 | 119.97 |
| summary | cache | 1 | 399.57 |
| summary | cache | 4 | 147.18 |
| summary | candidates | 1 | 409.97 |
| summary | candidates | 4 | 155.19 |

32 样本 × 1/2/4/8 线程的当前整合旧链基线保留在 `benchmarks/integrated`，本表是新链的小批量补测，不混用两次数据计算加速比。Python MC 边界在 AMD128 单独测量，不能与本机 CLI 相除。

## 内存与三组编译对照

`memory.json` 用 macOS `/usr/bin/time -l` 在独立进程测 seed 0、每配置 3 次，包含 CLI 及输出的峰值 RSS；不计入延迟表。F35 数据如下，单位 MiB：

| profile | 观测 | scan | cache | candidates |
|---|---|---:|---:|---:|
| legacy-minute-v1 | full | 41.69 | 46.31 | 46.25 |
| legacy-minute-v1 | summary | 18.09 | 24.75 | 22.42 |
| event-time-v2 | full | 41.78 | 48.66 | 46.33 |
| event-time-v2 | summary | 18.28 | 25.08 | 24.88 |

未测分配次数、峰值编译内存或独立候选容器占用；不作这些方面的收益声明。

同一源码另跑了当前三层无 MLIR、MLIR 验证但关闭 pass、开启 pass 的编译/加载/九次执行对照，分别见 [minute](../mlir-minute-20260925/README.md) 与 [O5](../mlir-o5-20260925/README.md)。这些运行开启 phase profile，用于机制和分段解释，不替代上面的未插桩时间。minute 总成本 2.0593 → 1.9729 s（降低 4.20%）；O5 0.5752 → 0.7682 s（增加 33.55%）。无 O5 样本数回本点。两份报告中的“现有编译链”均指本轮三层链；只有 compile-cost 的 old 指旧直达 Plan 链。

## 验证与复现

源码与工具链身份、输入/Plan/result 摘要位于 identity/runs/compile-cost/evidence JSON；profile 完整分段和批量记录邻接保存。严格语义测试先于性能测量；原 golden 和上游快照未改写。Linux CI 状态及绑定补测见本目录 acceptance 文件。

复现命令见 [依赖派遣文档](../../../../docs/dependency-dispatch.md)。独立内存测量命令：`python benchmarks/dependency_dispatch/measure_memory.py benchmarks/dependency_dispatch/results/macos-arm64-20260925`。所有数值仅支持保留 opt-in 实验的决定；完整事件回调执行、第二领域、正式 Agent patch/发布 API 与微架构优化仍在本里程碑之外。

## AMD128 Python MC 边界

源码 `49b226dd4b78267c87f52ebdaedbe258faff1951` 的 Linux wheel 在隔离临时目录离线重建，9 项绑定测试全部通过。32 个样本含重复 seed，1/2/4/8 线程、每配置预热后 3 次热缓存测量，整个 Python 调用中位数分别为 3422.01 ms, 2142.88 ms, 1607.25 ms, 1328.05 ms。冷缓存、原生分段、输入/扩展摘要与整进程峰值 RSS 见 `../amd128-binding-20260925.json`。逐样本完整结果跨缓存/线程完全一致；只使用显式指定的至多 8 线程，未作 128 核扩展性结论。该 MC API 沿用默认扫描，候选 API 的批量测试在 Rust 单独完成。
