# sim_engine_compiler

面向任务、资产与保障资源的业务模型编译器及离散事件运行时。首个领域是飞机机群任务与保障，原型通过 `spare_mvp` 的 canonical `simulation_inputs` 接入。

**当前状态：Python reference 与独立 Rust 单样本/批量 runtime 均已通过当前 Execution Plan 兼容范围。** B1 任务与日保障、B2 故障/维修/预防维修、B3 本地与组织库存/运输/取消返还均由独立 Plan runtime 执行；F35 43 天案例的 seed `0、1、7` 已完成旧模型 → Python reference → Rust 的差分闭环。Rust 批量执行共享只读 Plan、隔离每个样本的 RunState，并按输入 `sample_index` 稳定输出；Python 3.12 可通过 PyO3 绑定直接调用相同批量 API。

MLIR 资源依赖索引试点已贯通 F35 canonical 输入、`sim` 方言 pass、带反向依赖索引的 Execution Plan 和现有 Rust 执行器。三个 seed、三次重复的完整结果完全一致；守卫重检次数降低 95.73%，本轮编译、加载与九次运行总成本降低 4.26%。数据和适用边界见[试点记录](docs/mlir-resource-dispatch-pilot.md)。

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
3. 按 [实施路线](docs/roadmap.md) 完成第一个确定性纵向切片，再扩展兼容范围。

开发目标为 Python 3.12+。当前可在不安装依赖的情况下检查包入口：

```bash
PYTHONPATH=src python3.12 -c 'import sim_engine_compiler; print(sim_engine_compiler.__version__)'
```

如需包含 Rust 绑定的可编辑安装，可使用虚拟环境与 `uv`（Maturin 会编译原生扩展）：

```bash
python3.12 -m venv .venv
uv pip install --python .venv/bin/python -e .
```

ABM acceptance uses the pinned test extra and Rust 1.90.0:

```bash
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest tests/conformance tests/differential/test_abm_rust_runtime.py
cargo +1.90.0 test --locked --release --manifest-path rust/runtime/Cargo.toml
```

当前可使用 `scripts/compile_execution_plan.py` 和 MLIR 试点入口 `scripts/compile_mlir_execution_plan.py`；后者要求固定 LLVM/MLIR 23.1.1 插件。`scripts/run_reference_plan.py` 执行 Python reference，`rust/runtime` 的 `sim-engine-runtime` CLI 执行同一计划。Python 侧可调用 `sim_engine_compiler.run_plan(...)`、`sim_engine_compiler.run_batch(...)` 与 `sim_engine_compiler.run_canonical_batch(...)`。最后一个入口只接受上游 Adapter 生成的 canonical `simulation_inputs`，固定执行 `event-time-v2` summary，供 `spare_mvp` 的核心 Monte Carlo 路径使用；它不解释 Project JSON，也不生成分析投影。实现、三个手算切片和 F35 证据见 [Independent SimPy Reference Runtime Conformance](docs/b1-independent-reference.md)。[F35 43 天性能基线](benchmarks/spare_mvp_f35_43day/README.md)与[阶段 C 正式分段基准](benchmarks/stage_c/README.md)单独保留；语义验收与性能结论继续分开。

当前仓库还提供 `rust/compiler` 的 canonical-input AOT lowering 与版本化二进制 Plan 缓存。AMD128 的 Project→canonical 分段 profile、首次 miss 与 pre-Adapter Project 指纹命中结果见 [冷启动实验](benchmarks/cold_start/README.md)。该实验使用整合前的 v2 缓存；当前 v3 格式需重新测量。它没有实现 Rust Project Adapter；重复模型命中与第一次启动是两条不同的证据边界。

可行性研究阶段的 SIMLOX 外部效率对照方法及 `4700-3` 原始证据位置见 [SIMLOX 对照说明](docs/simlox-feasibility-benchmark.md)。这组案例没有 canonical 输入和语义差分，不属于本项目运行时性能验收。

本地[交互验证入口](demo/README.md)提供 B1、B3、F35 的固定案例对照：选择 seed、样本数和线程数，比较分钟推进与 O5，并在支持的组合下分别检查 MLIR 资源索引与 AOT Plan 缓存。它通过现有 CLI 执行引擎，展示逐样本首处分歧、编译/加载/初始化/执行耗时与资源检查计数；页面的一次计时只是交互诊断，不替代正式重复基准。

## 设计来源与证据边界

依据 2026-09-20 的讨论：[设计仿真引擎 and IR](chatgpt-conversation://6aaf8dfc-02e0-83ea-8eb1-460c5abf7b5f)。本项目已从上游提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` 导出固定 canonical 输入，并重新生成 seed `0、1、7` oracle；验收不依赖运行中的上游数据库。

## 三层 IR 与依赖派遣里程碑

Python 与 Rust AOT 的正式链路现为 canonical → Business → symbolic Core → layout → Plan；中间产物可独立重载、校验和修订。MLIR 直接接受持久化 Core，包括 Rust AOT 生成的 Core。详见[三层 IR 合同](docs/three-layer-ir.md)与[依赖派遣验收](docs/dependency-dispatch.md)。候选派遣需显式启用，性能结论按 profile 和观测级别分别报告。
