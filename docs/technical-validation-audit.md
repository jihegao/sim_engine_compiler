# 技术验证前的代码与证据审计

审计日期：2026-09-22。此文件记录只读代码检查和已有仓库证据；不把历史报告当成本轮重跑结果。

## 固定来源

| 来源 | 提交 | 本次使用边界 |
|---|---|---|
| `sim_engine_compiler/main` | `f59197cd884ef6514a2e212b79cd1b6118332211` | 初始本地源文件和历史 benchmark 快照 |
| `sim_engine_compiler/codex/event-time-v2-o5` | `4a2fc15b6c0aae723ba1dd7bdbdf54f6e05491dc` | 本轮非 benchmark 代码、文档、测试来源；历史性能报告另行只读检查 |
| `sim_engine_compiler/codex/observation-f35-hot-path` | `7563ca5ce1189f2cd969bdcea965af6e03671a4c` | 已发现分支身份，未完整审计 |
| `sim_engine_compiler/codex/spare-mvp-cold-start` | `fee9e81d37e4b4ea585f2eae79247882189ebf33` | 已发现分支身份，未完整审计 |
| F35 canonical fixture 的上游 `spare_mvp` | `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` | 仓库 manifest 冻结的输入来源；不读取活动数据库 |

F35 输入的规范化 SHA-256：`6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`。文件位于 `tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json`。

本地材料是逐文件获取并核验的源快照，不是完整 git checkout：非 benchmark 文件已更新至 O5 提交；benchmark 数据保留初始快照，相关说明按最终 source_manifest.json 核验。新增实验位于 `experiments/ir_validation`，不改变生产运行时语义。最终 manifest 应按文件记录来源与内容身份。

## 当前实现与目标的差距

| 目标 | main 当前代码事实 | 本轮验证需要区别的结论 |
|---|---|---|
| 三层 IR | `compiler/aircraft_support.py` 直接生成 `ir/plan.py` 中的 `ExecutionPlan`；Business/Core IR 尚未物化 | 新三层实验可验证设计机制，不能声称生产链路已经迁移 |
| 通用领域映射 | `domains/aircraft_support` 只有 README 与包入口；领域规则仍位于 compiler/reference | 第二领域必须使用相同核心操作与调度器；改标签或复制飞机运行时不足以证明通用性 |
| 独立执行器 | Python `SimpyReferenceRuntime` 与 Rust `Runtime` 都只读 Plan；旧模型位于 oracle 工具边界 | 已有独立性值得复用；独立实现相互一致仍不能自动证明业务正确 |
| 实际事件推进 | main 的 Python `_clock` 使用 `env.timeout(1)`；Rust `run` 使用 `minute += 1`，两者执行 15 个 phase；本轮 O5 快照另有保守跳时路径 | main 的性能基线不是纯事件内核，O5 也尚非直接事件回调；不应把语言收益解释为事件调度收益 |
| 通用执行计划 | Plan 版本为 `aircraft-support-plan/v1alpha2`，字段为 aircraft/missions/activities/components 等 | 当前计划为领域专用合同，不是通用状态、事件与资源指令集合 |
| 编译验证 | 支持部分 schema/profile/引用/局部 DAG 检查；`unsupported_features` 从空列表生成 | 不能凭该字段为空宣称所有输入行为均受支持；部分兼容归一化、跳过路径仍需覆盖 |
| 模型修订 | 有输入 digest、Plan fingerprint、source path 和冻结 dataclass | 尚无受限规则 patch、影响分析、增量编译及 IR-native 编辑闭环 |
| 共享计划、独立状态 | Rust 批量 API 使用共享只读 Plan，每样本独立状态，并保持 sample_index 顺序 | 可复验线程数、重复 seed、状态不泄漏；批量结果一致不等同线性扩展 |

### 语义接入边界

`scripts/export_spare_mvp_fixture.py` 实际调用上游：

```python
project = ProjectJsonExporter().export(raw)
inputs = SimulationAdapter(root).compile_scenario(project)["simulation_inputs"]
Draft202012Validator(schema).validate(inputs)
```

随后显式添加 `disable_visualization_frames=True` 并记录 manifest。本轮可复用冻结 canonical 输入，但不应重新实现 Project JSON 解释器，也不应将实验模型包装为已经过上游 Adapter 的真实 Project。

上游 ownership 文件为 `contracts/`、`src/spare_mvp_backend/project_payload.py`、`src/spare_mvp_contract/adapter.py`。本次在线读到的 Adapter blob SHA 为 `f78ea525ed8a2e631204bea1914e368befcae8b1`，这是当前默认分支内容，不是 F35 fixture 所用旧提交；两者不得混用来声称输入来源。

### 必须冻结的旧语义

- `legacy-minute-v1` 的 15 个 phase 顺序及下一分钟可见性。
- `stable-topological-serial`：本地作业图允许 DAG，但兼容执行为稳定拓扑串行。
- `legacy-sequential-v1`：随机采样顺序，包括适用性检查前的采样，属于合同。
- 起飞前替补与起飞后中止不同；不能因改为事件驱动而自动产生补充任务。
- 资源分阶段预约、库存归还、运输到达、取消一次结算与 horizon 边界。
- 故障暴露量递减的浮点行为，不能仅因代数等价就假设逐次递减与一次扣除位相等。

## 已有实验分支：不要忽略，也不要混入本轮测量

`codex/event-time-v2-o5` 已实现保守跳时：寻找下一可观测分钟，跨空区间推进倒计时，再执行原 15-phase 表。其报告称 F35 seed 0 从 61,920 个分钟迭代降到 1,609 个唤醒分钟；仍构建 1,609 次日历、检查 384,040 个唤醒候选，并保留 18,440,262 次组件倒计时操作。因此它仍非 transition-owned 持久事件回调内核。

其历史 AMD128 对照显示 O5 对既有优化分钟运行时的执行耗时降低 69.74%–81.62%；这是固定 F35、三 seed、full/summary 的历史报告，不是本轮新测量。来源：

- `benchmarks/hot_path/results/o5-event-time-v2-20260921/README.md`
- `benchmarks/hot_path/results/20260921-o5b-o5c-o5d-amd128/README.md`

后续候选 O5b 持久堆仍逐次扫描并协调状态，耗时反而增加 56.03%–72.65%，已拒绝；它没有验证真正由状态转移拥有 schedule/cancel 的设计。O5c 改善仅 0.71%–1.58%，未收录。O5d 在精确性守卫下批量推进倒计时改善 30.61%–41.16%，通过独立实验门槛，但该分支报告明确说明尚未合入 accepted runtime。不能宣称“加一个事件堆就必然更快”。

## 现有验收与缺口

仓库保存 B1 日保障、B2 故障维修、B2 预防维修、B3 组织库存等手算输入、Plan、结果和 oracle。F35 为 9 架飞机、104 个任务、13 个活动、424 个组件、18 个预防维修周期。已有文档报告 seeds 0/1/7 的旧模型 → Python → Rust 差分通过。

F35 的三个 gzip oracle 最初未随 UTF-8 快照取得，随后已通过 base64 文件接口补齐并核验 Git blob SHA。本轮可重新执行 Python/Rust 并与已保存的旧模型 oracle 做三方结果差分，但没有现场重新运行上游旧模型；这两个证据层级应明确区别。

本轮最有价值的新增证据为：规则/关系修改而非仅参数变化、第二领域使用相同调度器、动态备用机绑定、循环恢复、同刻竞争/取消/过期事件、精准等待者唤醒、模型修订隔离、拒绝未知操作、稀疏和密集负载各自的成本。

性能应分别记录编译、初始化、执行、结果构造和端到端时间，并同时显示访问计数。小合成模型的高倍加速不能外推到 F35、当前 O5 分支或工程级业务模型。若新内核采用新的时间/RNG/事务语义，应显式命名新 profile，保持与兼容性验证分开。

## 审计用主要代码身份

| main 文件 | blob SHA |
|---|---|
| `src/sim_engine_compiler/compiler/aircraft_support.py` | `45ab75d5cbd901baeedf8a4a02f13fa9aaec6aff` |
| `src/sim_engine_compiler/ir/plan.py` | `481150b7a921e63bb48502e8e40ca7b950280d5b` |
| `src/sim_engine_compiler/reference/simpy_runtime.py` | `65d696e66610c2ad3d12ecaa0b4bdddf04ee970e` |
| `rust/runtime/src/runtime.rs` | `c579f22bddeb776d6d2a38ae1f089c61d273297d` |
| `scripts/export_spare_mvp_fixture.py` | `ac842bbcb6cf5c2c1ea99327d335aaabdacd29be` |

`AGENTS.md` 中的“Rust remains a scaffold”已落后于源码及 README；本审计按实际可执行代码描述状态，其余开发边界继续适用。

## 本轮新增实验的独立对抗复核

`experiments/ir_validation/reference.py` 是独立扫描解释器：使用业务名称字典保存状态、对事件列表线性取最小、扫描全部过程查找受影响等待者，不导入 indexed executor 的转移或采样实现。它是清晰但有意低效的正确性参考及算法对照，不能将对它的加速比解释为对成熟仿真软件的优势。

`adversarial.py` 固定生成器种子，生成 100 个飞机/生产词汇的合法模型，每个使用 `0、17、4294967295` 三个仿真 seed。保存结果 `adversarial_results.json` 记录了：

- 300 个样本的独立扫描 Python、索引 Python、Rust 全部业务字段与 trace 精确一致。
- 容量守恒、库存守恒（开始即消耗）、owner/status/selected 对应、完成次数与 trace 数一致、关闭 trace 不改变状态。
- 15 个 Business 输入、7 个 Core 输入、8 个 Rust 序列化 Plan 输入拒绝项通过，包括未知操作、无效单位、引用、前驱环、后端不支持 profile 和 int64 范围。
- Core 专用 generation 复用案例：同一过程在 t=0 开始、t=2 中止、t=3 重启；旧 t=10 完成事件不能结束新一代。horizon=11 时新一代仍运行，horizon=14 时仅 t=13 完成；三后端一致。
- int64 最大 horizon 边界正确忽略 horizon 之外完成事件；库存加法溢出在三后端都明确失败。

复核中发现 Python 编译器原先接受超出 Rust int64 范围的整数。实验编译器已限定范围并复跑通过；生产兼容编译器未因此修改。Python API 执行编译器产生的类型化 Plan，没有提供不可信 JSON Plan 加载器；Rust CLI 承担独立校验的序列化边界。Python envelope/op 检查不能被描述为任意手工伪造 dataclass 的完整验证器。

第二领域证据应保持有限：当前两个 Business 词汇主要映射到同一任务、资产、资源、故障恢复子集。它证明这些模型可使用无领域分支的相同内核，尚不能证明复杂生产物流、运输网络或其他行业主要规则均可无需扩展内核地表达。当前没有新增业务操作名称便自动生成语义、运行中热修改或真正增量编译的证据。
