# sim_engine_compiler

面向任务、资产与保障资源的业务模型编译器及离散事件运行时。首个领域是飞机机群任务与保障，原型通过 `spare_mvp` 的 canonical `simulation_inputs` 接入。

**当前状态：项目结构与设计基线已建立，并捕获了 `spare_mvp` F35 43 天的分钟/编译结构/SimPy 上游基准；导入器、IR schema、编译器和独立执行器尚未实现。** Python 包目前只有命名空间和基准验证工具；Rust 目录保留实现边界。本文的流水线描述目标架构，不表示本项目已能运行仿真。

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
│   └── adr/0001-layered-ir.md       首个架构决策
├── contracts/README.md              合同清单、版本、身份与诊断设计
├── src/sim_engine_compiler/
│   ├── ir/                         三层 IR 类型（待实现）
│   ├── compiler/                   编译 passes、依赖分析、缓存（待实现）
│   ├── domains/aircraft_support/    领域实体、规则、指标（待实现）
│   ├── reference/                  独立 Python 执行器（待实现）
│   └── integrations/spare_mvp/      上游合同接入（待实现）
├── rust/runtime/                    Rust 内核预留，阶段 C 建 crate
├── tests/
│   ├── fixtures/                   小案例、输入来源、golden 产物
│   ├── conformance/                合同、不变量、可手算案例
│   └── differential/               旧模型 / Python / Rust 首处分歧
└── benchmarks/                     分段计时、原始数据与环境信息
```

## 从哪里开始

1. 阅读 [架构](docs/architecture.md) 与 [架构决策](docs/adr/0001-layered-ir.md)。
2. 按 [阶段 A 清单](docs/semantic-baseline.md) 固定上游提交、输入快照和旧模型行为。
3. 按 [实施路线](docs/roadmap.md) 完成第一个确定性纵向切片，再扩展兼容范围。

开发目标为 Python 3.12+。当前可在不安装依赖的情况下检查包入口：

```bash
PYTHONPATH=src python3.12 -c 'import sim_engine_compiler; print(sim_engine_compiler.__version__)'
```

如需可编辑安装，可使用虚拟环境：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
```

目前没有本项目自己的仿真 CLI 或执行器。已实跑的 [F35 43 天对照基线](benchmarks/spare_mvp_f35_43day/README.md)属于上游 oracle；Rust 工具链、PyO3 和其他运行依赖在相应实现阶段选型并锁定。

## 设计来源与证据边界

依据 2026-09-20 的讨论：[设计仿真引擎 and IR](chatgpt-conversation://6aaf8dfc-02e0-83ea-8eb1-460c5abf7b5f)。本轮已读取完整讨论；未访问到上游 `spare_mvp` 源码和 canonical 输入快照。讨论提到的历史性能数据及兼容行为尚未在本项目复测，不能作为验收通过依据。
