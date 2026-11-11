# 航空保障领域案例库与 IR 编译运行发布包

`sim_engine_compiler` 维护航空任务、飞机、组件、维修、备件和保障资源的
可复现案例与语义基准，将业务模型经 **Business IR → Core Simulation IR →
Execution Plan** 编译，由独立 Python reference / Rust runtime 执行，并交付
可安装的 CLI/SDK、版本化模型包及验收证据。

## 项目交付与边界

| 交付物 | 本项目负责的内容 |
| --- | --- |
| 航空保障领域案例库 | 需求、参数与单位、来源版本、输入、Oracle、关键事件/账本断言和复现入口；复用现有案例来源与索引 |
| IR 编译运行发布包 | 领域校验、三层 IR、独立执行器、CLI/SDK、`.simpack`、版本与兼容迁移合同 |
| 验收与发布证据 | 案例×profile×后端支持矩阵、差分结果、产物指纹、安装运行记录及已知限制 |

案例库范围与执行支持范围分别记录。`simulation-case-library` 的 Golden Chains
和 `simlox/main` 的原生案例通过固定版本、路径和指纹关联；不另造一份案例解释器，
也不把 SIMLOX 案例已有输入输出等同于本发布包支持。上游 Project 继续只经
`integrations/spare_mvp` 的 canonical `simulation_inputs` 边界接入。

Plugin / Cloud 负责自然语言交互、工具集成、浏览器适配、保存与展示，是发布包的
消费端。本项目提供合同、模型包和可验证结果；消费端部署、浏览器验收及计费准入
各自跟踪。**本项目的发布门槛与 Plugin 联合验收分开**，不以原生测试代替浏览器
测试，也不为发布原生包默认新增云端执行服务。

## 本轮发布范围与验收目标

以下是待完成的发布目标，不表示已经实现或通过验收。完整工作包、依赖与分类见
[本轮收口计划](docs/scope-closure-plan-20261111.md)；历史阶段路线不扩大本轮门槛。

- **案例资产：**固定 GC-01-A01、GC-02-A02、GC-03-A03、GC-12-A12、GC-13-A13
  的需求、输入、Oracle、三层 IR 与运行断言；补充可靠性小例。复用 #18 已交付的
  非 GUI 原生案例目录，区分来源案例、可编译案例和已验证案例，不要求本轮支持全部原生案例。
- **航空保障语义：**多架次与生命周期、编队最低起飞数量、跨机型联合资源完整性、
  任务依赖、独立 LRU 实例故障与维修。整机下不同分系统默认串联，A/B 必须都完好；
  只有相同组件实例的冗余组使用 `k_out_of_n`（如 A×2 的 `k=1,n=2`）。
  不引入 `failure_threshold`，不以调整单体 MTBF/故障率替代冗余逻辑；旧字段与包须显式迁移或拒绝。
- **编译运行包：**复用 v0.1 已有入口，在现有 Linux x86_64、Python ≥3.12 的发行
  边界内完成新增语义的版本、安装和回归验收。索引 Plan 的 bundle 支持、第二领域、
  完整 WASM 产品和新性能收益均不列入本轮承诺。
- **发布通过条件：**五案例和可靠性正反例完整通过三层 IR 与 Python/Rust 行为
  验收；既有 B1/B2/B3、F35 及受影响 profile 回归通过；在仓库外安装候选包后完成
  示例、修改、seal、validate、compile、run、batch、diff；保存版本、指纹、命令与断言证据。
  版本号/tag 在候选冻结时确定，未运行或豁免不记为通过。

| 分类 | 当前 Issue / PR | 处理原则 |
| --- | --- | --- |
| 当前必须完成 | [#559](https://github.com/jihegao/sim_engine_compiler/issues/559)、[#560](https://github.com/jihegao/sim_engine_compiler/issues/560)、[PR #561](https://github.com/jihegao/sim_engine_compiler/pull/561)、[#18](https://github.com/jihegao/sim_engine_compiler/issues/18) 的既有案例资产登记 | 以五案例、可靠性语义和发布包验收收口；#561 不能单独代表 #560 全部完成，#18 全变体不作发布门槛 |
| 后续扩展 | [#10](https://github.com/jihegao/sim_engine_compiler/issues/10)、[#11](https://github.com/jihegao/sim_engine_compiler/issues/11) 的完整范围；[#549](https://github.com/jihegao/sim_engine_compiler/issues/549)、[#550](https://github.com/jihegao/sim_engine_compiler/issues/550)、[#551](https://github.com/jihegao/sim_engine_compiler/issues/551)、[PR #554](https://github.com/jihegao/sim_engine_compiler/pull/554)、[PR #555](https://github.com/jihegao/sim_engine_compiler/pull/555) | 复用已有基础身份/查询能力；完整 SysML、诊断、ABM、DES、WASM 与队列草稿分别验收 |
| 独立研究 | [#3](https://github.com/jihegao/sim_engine_compiler/issues/3)、[#6](https://github.com/jihegao/sim_engine_compiler/issues/6)、[#13](https://github.com/jihegao/sim_engine_compiler/issues/13) | GPU/统计加速、CPU 优化与风电基准不阻塞本轮发布；历史负面结果保留 |

[Linear 项目](https://linear.app/jhgao/project/sim-engine-compiler-466f038a4988)
维护分类与阶段；[JHG-120](https://linear.app/jhgao/issue/JHG-120) 对应本仓库主线，
[JHG-119](https://linear.app/jhgao/issue/JHG-119) 与
[JHG-118](https://linear.app/jhgao/issue/JHG-118) 保留消费端和跨仓库联合验收。

## 已交付基线与历史证据

航空保障20条候选链另有显式 opt-in 的
[bounded event profile](docs/aircraft-bounded-events.md)：Business/Core/Plan、
亚分钟截止、资源、维修与库存响应；Python reference 专用，独立于现有产品入口。
其中5条采用外生故障或损伤返场输入，不能解释为原生随机过程等价。

既有默认入口、能力/验收矩阵及性能采用状态见
[595cb5e 基线说明](docs/engine-baseline-595cb5e-v1.md)。特别是 PR #9 的共享
PreparedBatchPlan 已进入普通 aircraft 批量默认路径，但历史 J35 全线程性能门槛
未通过；历史报告中的“未合并默认”不再表示当前代码状态，也不代表当前版本的新测量。

## v0.1 可安装产品入口（Issue #29）

`sim-engine-compiler` wheel 提供 `sim-engine` 命令和等价 Python SDK，
覆盖 `inspect / validate / seal / compile / run / batch / diff`。
安装后的 `sim-engine example DIR` 在目标目录生成可编辑的 synthetic B1
Business IR 与初始 `.simpack`；修改 Business payload 后显式 `seal`、
`validate`、`compile` 即可产生新 bundle 并运行，不需要仓库脚本或修改 Rust。
完整的版本支持矩阵、bundle 失效规则、示例命令和 Agent 操作合同见
[v0.1 产品合同](docs/v01-product-contract.md)与
[Agent 工具合同](docs/agent-v01-tool-contract.md)。

v0.1 bundle 限定为未带资源派遣索引的 aircraft Plan。已有索引 Plan
实验及其运行时能力不因此改变；当前身份检查尚不能证明索引内容与其
Plan fingerprint 的关联，产品入口会明确拒绝该组合。

**既有验收范围：Python reference 与独立 Rust 单样本/批量 runtime 已通过既有 Execution Plan 兼容范围，不代表上述本轮新增语义已验收。** B1 任务与日保障、B2 故障/维修/预防维修、B3 本地与组织库存/运输/取消返还均由独立 Plan runtime 执行；F35 43 天案例的 seed `0、1、7` 已完成旧模型 → Python reference → Rust 的差分闭环。Rust 批量执行共享只读 Plan、隔离每个样本的 RunState，并按输入 `sample_index` 稳定输出；Python 3.12 可通过 PyO3 绑定直接调用相同批量 API。

MLIR 资源依赖索引试点已贯通 F35 canonical 输入、`sim` 方言 pass、带反向依赖索引的 Execution Plan 和现有 Rust 执行器。三个 seed、三次重复的完整结果完全一致；守卫重检次数降低 95.73%，该历史试点的编译、加载与九次运行总成本降低 4.26%。数据和适用边界见[试点记录](docs/mlir-resource-dispatch-pilot.md)。

```text
spare_mvp Project JSON
  → 上游 ProjectJsonExporter / SimulationAdapter
  → canonical simulation_inputs
  → Business IR → Core Simulation IR → Execution Plan
                                      ├─ Python reference
                                      └─ Rust runtime
                                           → Result / Trace / Diagnostics
```

Python 负责建模、验证、编译、诊断及独立参考执行；Rust 负责数组状态、事件调度、资源事务及样本并行。模型更新通常重新生成执行计划，无需每次重新编译 Rust 二进制。

## 初始目录

```text
.
├── AGENTS.md                       开发边界与证据要求
├── pyproject.toml                  Python 包基础配置
├── docs/
│   ├── architecture.md             模块职责、依赖方向、运行边界
│   ├── semantic-baseline.md         兼容行为与待核验清单
│   ├── roadmap.md                   阶段 A–E 与首批交付切片
│   ├── simlox-feasibility-benchmark.md  可行性阶段的 SIMLOX 外部效率对照方法
│   └── adr/0001-layered-ir.md       首个架构决策
├── contracts/README.md              合同清单、版本、身份与诊断设计
├── src/sim_engine_compiler/
│   ├── ir/                         可持久化 Business/Core IR、Execution Plan 合同
│   ├── compiler/                   canonical lowering 与索引化 Execution Plan
│   ├── domains/aircraft_support/    领域插件边界（待从 B1 lowering 提取）
│   ├── reference/                  独立 SimPy 执行器与首处分歧工具
│   └── integrations/spare_mvp/      上游文件边界与说明
├── rust/runtime/                    独立 Rust 单样本执行内核与 CLI
├── tests/
│   ├── fixtures/                   小案例、输入来源、golden 产物
│   ├── conformance/                合同、不变量、可手算案例
│   └── differential/               旧模型 / Python / Rust 首处分歧
└── benchmarks/                     分段计时、原始数据与环境信息
```

当前已补齐 canonical 工作时长与组件引用的 Python/Rust 一致校验，详见[输入校验合同](docs/strict-work-input-validation.md)。MC/O5/MLIR/v3 缓存整合后的新基线使用[独立测量入口](benchmarks/integrated/README.md)；不复用历史性能数值作为本次结论。

## 从哪里开始

1. 阅读 [架构](docs/architecture.md) 与 [架构决策](docs/adr/0001-layered-ir.md)。
2. 按 [阶段 A 清单](docs/semantic-baseline.md) 固定上游提交、输入快照和旧模型行为。
3. 按[本轮收口计划](docs/scope-closure-plan-20261111.md)完成航空保障案例与发布验收；[实施路线](docs/roadmap.md)保留历史阶段和后续研究上下文。

开发目标为 Python 3.12+。当前可在不安装依赖的情况下检查包入口：

```bash
PYTHONPATH=src python3.12 -c 'import sim_engine_compiler; print(sim_engine_compiler.__version__)'
```

如需包含 Rust 绑定的可编辑安装，可使用虚拟环境与 `uv`（Maturin 会编译原生扩展）：

```bash
python3.12 -m venv .venv
uv pip install --python .venv/bin/python -e .
```

已有 ABM 扩展的独立验收使用固定 test extra 和 Rust 1.90.0；该扩展不属于本轮航空保障发布承诺：

```bash
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest tests/conformance tests/differential/test_abm_rust_runtime.py
cargo +1.90.0 test --locked --release --manifest-path rust/runtime/Cargo.toml
```

当前可使用 `scripts/compile_execution_plan.py` 和 MLIR 试点入口 `scripts/compile_mlir_execution_plan.py`；后者要求固定 LLVM/MLIR 23.1.1 插件。`scripts/run_reference_plan.py` 执行 Python reference，`rust/runtime` 的 `sim-engine-runtime` CLI 执行同一计划。Python 侧可调用 `sim_engine_compiler.run_plan(...)`、`sim_engine_compiler.run_batch(...)` 与 `sim_engine_compiler.run_canonical_batch(...)`。最后一个入口只接受上游 Adapter 生成的 canonical `simulation_inputs`，固定执行 `event-time-v2` summary，供 `spare_mvp` 的核心 Monte Carlo 路径使用；它不解释 Project JSON，也不生成分析投影。实现、三个手算切片和 F35 证据见 [Independent SimPy Reference Runtime Conformance](docs/b1-independent-reference.md)。[F35 43 天性能基线](benchmarks/spare_mvp_f35_43day/README.md)与[阶段 C 正式分段基准](benchmarks/stage_c/README.md)单独保留；语义验收与性能结论继续分开。

当前仓库还提供 `rust/compiler` 的 canonical-input AOT lowering 与版本化二进制 Plan 缓存。AMD128 的 Project→canonical 分段 profile、首次 miss 与 pre-Adapter Project 指纹命中结果见 [冷启动实验](benchmarks/cold_start/README.md)。该实验使用整合前的 v2 缓存；当前 v3 格式需重新测量。它没有实现 Rust Project Adapter；重复模型命中与第一次启动是两条不同的证据边界。

可行性研究阶段的 SIMLOX 外部效率对照方法及 `4700-3` 原始证据位置见 [SIMLOX 对照说明](docs/simlox-feasibility-benchmark.md)。这组案例没有 canonical 输入和语义差分，不属于本项目运行时性能验收。

SIMLOX 2017 的事件循环、重复实验种子、分布采样和提前停止条件见
[REA/Ghidra 静态分析报告](docs/simlox-2017-static-analysis.md)。报告保留代码观察、
手册规则及未验证范围；这些静态证据不构成本项目的原生 SIMLOX 语义等价或性能验收。

本地[交互验证入口](demo/README.md)提供 B1、B3、F35 的固定案例对照：选择 seed、样本数和线程数，比较分钟推进与 O5，并在支持的组合下分别检查 MLIR 资源索引与 AOT Plan 缓存。它通过现有 CLI 执行引擎，展示逐样本首处分歧、编译/加载/初始化/执行耗时与资源检查计数；页面的一次计时只是交互诊断，不替代正式重复基准。

## 设计来源与证据边界

依据 2026-09-20 的讨论：[设计仿真引擎 and IR](chatgpt-conversation://6aaf8dfc-02e0-83ea-8eb1-460c5abf7b5f)。本项目已从上游提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` 导出固定 canonical 输入，并重新生成 seed `0、1、7` oracle；验收不依赖运行中的上游数据库。

## 三层 IR 与依赖派遣里程碑

Python 与 Rust AOT 的正式链路现为 canonical → Business → symbolic Core → layout → Plan；中间产物可独立重载、校验和修订。MLIR 直接接受持久化 Core，包括 Rust AOT 生成的 Core。详见[三层 IR 合同](docs/three-layer-ir.md)与[依赖派遣验收](docs/dependency-dispatch.md)。候选派遣需显式启用，性能结论按 profile 和观测级别分别报告。

## 离线审阅数据（#10 首个切片）

`python -m sim_engine_compiler.review export <business-or-core.json>` 从已保存、
已校验的 IR 导出版本化设计审阅 JSON。它复用 PR20 的身份与 bundle 校验，
不执行模型、不猜测独立 Core 的原始 Business，也不实现 SysML 渲染。
支持矩阵、来源限制及离线 API/CLI 示例见[审阅数据合同](docs/review-data-v1.md)。
身份与审阅数据合同已随 PR20、PR23 合入 `main`；完整规则语义与 SysML 仍未交付。

## 离线运行追溯（#11 有界切片）

`python -m sim_engine_compiler.trace_query <result.json> --request <request.json>
--plan <plan.json>` 只查询已保存事件，支持筛选、分页、事件输出预算和稳定 ID
解析。设计关联复用原始 bundle 的身份与 #10 审阅校验；缺失原因保持未知。
本切片仅验收 Python reference 分钟 profile，明确不代表 Rust/O5 采集验收或
完整因果诊断。支持矩阵、证据限制和离线示例见[查询合同](docs/trace-query-v1.md)。
