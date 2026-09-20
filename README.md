# sim_engine_compiler

面向任务、资产与保障资源的业务模型编译器及离散事件运行时。首个领域是飞机机群任务与保障，原型通过 `spare_mvp` 的 canonical `simulation_inputs` 接入。

**当前状态：Independent SimPy Reference Runtime Conformance 已完成。** B1 任务与日保障、B2 故障/维修/预防维修、B3 本地与组织库存/运输/取消返还均由独立 Execution Plan runtime 执行；F35 43 天案例的 seed `0、1、7` 已与固定旧模型 oracle 对齐。Rust 目录仍是预留边界。

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
│   ├── ir/                         Execution Plan 合同；Business/Core IR 待补
│   ├── compiler/                   canonical lowering 与索引化 Execution Plan
│   ├── domains/aircraft_support/    领域插件边界（待从 B1 lowering 提取）
│   ├── reference/                  独立 SimPy 执行器与首处分歧工具
│   └── integrations/spare_mvp/      上游文件边界与说明
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

当前可使用两个文件边界 CLI：`scripts/compile_execution_plan.py` 将 canonical JSON 编译为计划，`scripts/run_reference_plan.py` 只执行已序列化计划。实现、三个手算切片和 F35 证据见 [Independent SimPy Reference Runtime Conformance](docs/b1-independent-reference.md)。[F35 43 天性能基线](benchmarks/spare_mvp_f35_43day/README.md)单独保留；本阶段结论是语义一致，不把 SimPy reference 宣称为性能目标。

## 设计来源与证据边界

依据 2026-09-20 的讨论：[设计仿真引擎 and IR](chatgpt-conversation://6aaf8dfc-02e0-83ea-8eb1-460c5abf7b5f)。本项目已从上游提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` 导出固定 canonical 输入，并重新生成 seed `0、1、7` oracle；验收不依赖运行中的上游数据库。
