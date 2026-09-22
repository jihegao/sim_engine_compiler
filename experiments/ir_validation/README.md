# Business IR 技术验证案例集

这是一组可复现的技术实验，目标是检验：业务规则能否编译为独立计划、不同语言执行器能否保持语义一致、事件和局部唤醒能否减少无关计算、以及同一内核能否覆盖飞机和生产设备的共同子集。

请先阅读同目录 `REPORT_zh.md` 的结论与证据边界。`SPEC.md` 是新增实验语义的完整定义。

## 两条验证链路

1. **既有语义回归**：冻结的 `spare_mvp` canonical 输入 → 仓库现有编译器 → Python reference / Rust legacy / Rust event-time。F35 使用保存的上游 oracle；本轮没有启动旧项目数据库或重新解释 Project JSON。
2. **新架构可行性**：合成 Business IR → Core IR → 不可变 Plan → 独立扫描 reference / Python 索引执行器 / Rust 事件执行器。显式使用 `ir-native-event-v1`，不声称兼容旧飞机模型的分钟阶段、故障分布或分阶段资源预约。

新增原型支持有限状态资产、运行时候选选择、原子容量与库存获取、库存到达、DAG 前驱、循环任务与故障修复、同刻 FIFO、generation 失效事件、稳定身份随机流和样本并行。支持的第二领域为生产设备任务与停机恢复的共同子集。

本次没有实现完整 canonical → 三层 IR 迁移、持久编译缓存、增量编译、运行中编辑或生产级 Monte Carlo RNG。其余限制见报告。

## 环境与运行

Python 3.12+；Rust stable（本次实测 rustc/cargo 1.98.1）。新原型 Python 仅依赖标准库；已有语义回归需要 SimPy 4.1.2。Rust 的精确依赖由两个 `Cargo.lock` 固定。

在仓库根目录执行：

```bash
python3 -m pip install simpy==4.1.2
cargo build --locked --release --manifest-path experiments/ir_validation/rust_kernel/Cargo.toml
python3 experiments/ir_validation/run_cases.py
python3 experiments/ir_validation/test_review_fixes.py
python3 experiments/ir_validation/adversarial.py --rust experiments/ir_validation/rust_kernel/target/release/ir-validation-kernel
python3 experiments/ir_validation/benchmark.py --repeats 7
```

上述命令重建新架构案例、随机差分与基准。基准必须在前面的正确性检查通过后运行。输出中保留逐次纳秒计时、环境信息和语义等价断言。共享主机的绝对耗时会变化。

检查原始提交的文件完整性时，在重新生成结果之前执行：

```bash
python3 experiments/ir_validation/verify_manifest.py
```

它逐项验证 `files` 中的存在性、大小及 SHA-256，并在 git checkout 中核对文件受版本管理；独立快照可用 `--inventory` 提供仓库路径 JSON 数组。清单记录的是交付文件子集，不包含自身、构建目录或传输中间文件；`build_artifacts` 仅为实测二进制身份元数据，不要求交付二进制。重新生成结果后，原始结果文件的哈希可能变化。

PR #1 评审修订：领域 schema 和 lowering 已提取到 `domain_packages/`，调用方通过 `DomainRegistry` 注入扩展，`generic.py` 不包含具体领域名称或字段映射。`test_review_fixes.py` 通过独立 `work_orders` 领域、键顺序不变性和清单损坏探针验证这三项修复。原报告的性能数字仍来自评审前测量，本次修订只复跑相关正确性验证。

已有飞机模型回归：

```bash
cargo build --locked --release --manifest-path rust/runtime/Cargo.toml --lib --bins --features python
python3 experiments/ir_validation/legacy_cases.py \
  --rust-binary rust/runtime/target/release/sim-engine-runtime \
  --native-library rust/runtime/target/release/libsim_engine_runtime.so \
  --f35 --run-repository-suite --benchmark-repeats 3 --paired-repeats 5
```

`--native-library` 是 Linux 的本次路径；其他系统使用对应的动态库文件名，或省略此参数并按原仓库 README 安装 Python 绑定。原仓库的 `rust-toolchain.toml` 指定 1.90.0，本次直接使用 1.98.1 工具链；需要同版本复现时可用 `cargo +1.98.1`。结果保留合法案例与非法输入探测两类结果：现有入口的三个已知校验缺口被报告为发现，不应将整份 JSON 解读为全绿验收。

## 文件导航

| 文件 | 内容 |
|---|---|
| `REPORT_zh.md` | 中文结论、数据表、限制与后续验收门槛 |
| `SPEC.md` | 新 profile 的时间、资源、循环、随机与结果合同 |
| `generic.py` | 注入式编译入口、Core/Plan 编译与 Python 索引执行器 |
| `domain_packages/` / `validation.py` | 独立领域适配器、注册表与通用校验工具 |
| `reference.py` | 独立、具名状态和全扫描参考解释器 |
| `rust_kernel/` | Rust 堆调度、紧凑状态、共享计划和样本并行 |
| `cases.py` / `run_cases.py` | 手算案例、变形检查、错误输入拒绝 |
| `adversarial.py` | 随机模型、三执行器差分、资源不变量、generation 边界 |
| `legacy_cases.py` | 既有 canonical 合法/非法案例、F35 与旧测试套件 |
| `benchmark.py` | 分段计时、扫描消融、局部/集中竞争、稀疏时域、批量运行 |
| `results/cases/` | 每个案例的原始输入、三层表示、预期与三个执行器完整轨迹 |
| `results/case_results.json` | 案例逐项判定及计数 |
| `results/benchmark_results.json` | 性能逐次原始记录 |
| `adversarial_results.json` / `legacy_results.json` | 对抗检查与既有语义证据 |
| `source_manifest.json` | 原始仓库提交、逐文件 blob 身份与快照范围 |
| `validation_manifest.json` | 本次实验源文件、结果文件与构建产物身份 |
| `verify_manifest.py` | 交付清单的存在性、大小、哈希与仓库成员校验 |
| `test_review_fixes.py` / `results/review_fix_results.json` | 三项评审问题的9项回归验证及结果 |

## 来源与修改边界

原始可执行代码固定在 `jihegao/sim_engine_compiler` 的
`4a2fc15b6c0aae723ba1dd7bdbdf54f6e05491dc`（`codex/event-time-v2-o5`）。本次实测使用经 blob 校验的源文件快照；独立归档包不含 `.git`，并省略了不参与本轮复现的部分历史性能档案。新增实验集中在本目录，审计说明另在 `docs/technical-validation-audit.md`。生产编译器和运行时源码没有被本次原型替换。

上游真实业务输入来源为 `spare_mvp` 的 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`。保存的 fixture manifest 含 Adapter、schema 和输入指纹。合成案例独立标记，不冒充上游真实样本。
