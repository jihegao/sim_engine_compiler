# 实施路线与验收

当前已完成项目结构、F35 上游基准、Independent SimPy Reference Runtime Conformance，以及阶段 C 的独立 Rust 单样本与批量执行内核、稳定排序、Python 绑定和正式分段基准。2026-09-24 另完成一个 opt-in MLIR 资源依赖索引试点：F35 三组对照的完整结果一致，9 次运行总成本降低 4.26%。详细证据见 [独立 reference conformance](b1-independent-reference.md)、[阶段 C 基准](../benchmarks/stage_c/README.md)和[MLIR 试点](mlir-resource-dispatch-pilot.md)。完整 Business/Core IR 尚未物化。

## 阶段路线

| 阶段 | 交付范围 | 退出条件 |
|---|---|---|
| A 语义基线 | 上游身份、输入快照、行为覆盖表、时间/RNG/资源/结果合同 | 首个切片的旧行为有可重跑 oracle，未支持范围明确 |
| B Python 编译执行 | 三层 IR、passes、独立 Plan、参考执行器、trace 与差分 | 同输入/profile/随机 tape 的关键事件、资源账本和末态一致；不变量通过 |
| C Rust 内核 | Plan 加载、事件堆、数组状态、资源事务、RNG、批量执行、Python 绑定 | 与参考执行器逐样本一致；内存与性能收益有可复核原始证据 |
| D Agent 编辑闭环 | IR-native 修订、受限 patch、影响分析、增量编译、对照结果 | 未知操作被拒绝；变更可追溯且不影响既有运行版本 |
| E 第二领域包 | 车队或生产设备保障之一 | 不修改核心调度器即可表达主要规则；领域能力可独立测试 |

## 首批交付切片

### A1：固定输入和语义 oracle

产物：输入来源 manifest、上游 revision、schema 引用、确定性小样例、phase 表、旧模型 trace 与运行命令。先完成 [语义基线](semantic-baseline.md) A01/A02，再补齐首个切片涉及的派遣、保障、资源及结果规则。旧模型仅存在于 oracle 工具边界。

### B1：最小确定性纵向切片

模型建议为两架飞机、一个任务名额、一个保障节点、一个维修人员；用固定故障与维修时长触发资源占用、完工、释放和备用机选择。确切时间线由 A1 的语义决定，不在骨架阶段猜测。

已贯通 canonical fixture → Plan → serialized file → independent SimPy → Result/Trace。当前尚未单独物化 Business/Core IR 文件，compiler pass 直接构造 Plan。任务、日保障、稳定串行步骤和容量资源已通过手算案例与旧模型 oracle。

### B2：故障、时钟与随机回放

加入组件树、飞行暴露量、版本化计时器、维修与换件、采样请求 tape。先比较请求身份与首次分歧，再实现完整兼容 RNG。检验地面暂停、跨航次继续及取消后的旧事件。

已完成：故障采样保持旧模型的“适用性判断前先抽样”顺序；维修完成后按同一流重采样；预防维修按日历、飞行小时和起落循环生成。跨 macOS/Linux 的 `libm` 指数结果只允许末位浮点容差，事件分钟严格比较。

### B3：完整兼容范围与增量唤醒

覆盖 daily-v1、稳定串行作业、组织资源分配、库存/运输/取消、时间条件唤醒及指标。建立 read/write 依赖检查，防止状态改变遗漏等待者。兼容覆盖表全部处置后才能宣称指定范围通过。

已完成当前案例范围：本地库存、纵向与横向预编译供应路线、运输到达唤醒、取消预约返还及最终库存账本。通用 read/write 反向依赖表仍属于后续 Core IR 工作。

### B4：缓存与分段基准

冻结指纹与参数失效规则，报告冷编译、热加载、初始化和执行。确认 summary/debug 结果等价。具备独立语义基线后才进入 Rust 性能迁移。

已完成 `summary/full` 观测隔离和 F35 seeds `0、1、7` 差分：`summary` 不 materialize
trace 事件 JSON，但保留相同随机请求、metrics 与终态。执行热路径计时和火焰图表明当前
主要成本是逐分钟 mission/job/component 扫描及其 Plan spec/字符串克隆与 Map 操作，
而不是 trace JSON；证据见 `benchmarks/hot_path/README.md`。

实验分支新增 Rust canonical-input AOT compiler 和版本化 Plan 缓存（整合后格式 `sim-engine-plan-cache/v3`）：五个固定
fixture 与 Python Plan 结构一致，Project 指纹命中可在 Adapter 前加载 Plan。AMD128 30 次
中位结果为整合前 v2 缓存命中并执行 O5 summary 的进程墙钟 `88.339 ms`；当前 v3 格式尚未重新测量。第一次启动仍受 Python
Project export/Adapter 的 `~0.72 s` 主导。证据和未实现的 Rust Adapter 边界见
`benchmarks/cold_start/README.md`。

可行性研究可用 SIMLOX 2017 的四个原生示例作为外部效率参照：在 `4700-3` 固定 1000 次重复仿真、8 线程、每案例三次并取中位数。输入指纹、运行参数、两轮计时和异常边界见 [SIMLOX 对照方法](simlox-feasibility-benchmark.md)。这些示例没有与本项目 canonical 输入配对，不构成语义或运行时性能验收。

### B5：MLIR 资源依赖索引试点（已完成，opt-in）

采用 LLVM/MLIR 23.1.1，在小型 `sim` Core IR 投影上实现资源依赖分析 pass。Rust 执行器消费可选反向索引，只复用依赖未变化的等待作业阻塞检查；事件顺序和 RNG 行为保持原样。

整合前的真实 F35 canonical 输入 → `sim` MLIR pass → Execution Plan → Rust 执行器链路已完成三组对照：seeds `0、1、7` 各运行三次，full `RunResult` 完全一致。动态 guard 检查从 1,005,081 降至 42,936，九次运行的编译、加载与执行总成本降低 4.26%。这些数字属于旧计划和旧资源语义；MC 整合后的组合须重新差分和计时。完整限制和 raw evidence 见[MLIR 试点记录](mlir-resource-dispatch-pilot.md)。这项结果不代表完整 IR 物化或一般硬件收益；LLVM codegen/JIT/GPU 不在本里程碑。

### C1：基于 F35 热路径的优化（O0/O1/O3/O4a/O5a/O6 已验收）

执行顺序与逐项验收见 [观测隔离与 F35 热路径优化计划](performance-optimization-plan.md)。
先补齐测量保护、消除三个 mission phase 的无效深克隆，再预计算静态关系、迁移故障状态数组，
随后按新 profile 评估活动集合。O5a 已作为独立 `event-time-v2` 语义 profile 验收；O5d 仍是待独立集成的候选，完整 callback 调度与 microstep 收敛尚未实现。
O0–O6 的实现与证据见[热路径报告](../benchmarks/hot_path/README.md)。O5a 新增独立 `event-time-v2` profile，以保守唤醒日历跳过空分钟，并在唤醒时执行 canonical phase 表；F35 三 seed、双观测及边界差分精确一致，原 AMD128 报告中的稳定会话改善为 69.74%–81.62%。O5b/O5c 候选已拒绝或不收录；O5d guarded continuous advance 保留为待独立集成候选，原始证据见[O5 实验记录](../benchmarks/hot_path/results/20260921-o5b-o5c-o5d-amd128/README.md)。O7 clone-elision 候选通过语义与目标 phase 验证，但未达整体墙钟收录门槛，见[O7 报告](../benchmarks/hot_path/results/20260920-o7-dispatch-clone-elision/README.md)。

## 测试分工

| 目录 | 检查目标 |
|---|---|
| `tests/conformance` | schema/类型/单位/引用、操作能力、手算案例、资源与库存守恒、排序、终止 |
| `tests/differential` | canonical 身份一致、随机请求一致、业务事件与账本一致、首处分歧定位 |
| `tests/fixtures` | 合成案例、canonical 快照、来源 manifest、预期输出及重建步骤 |
| `benchmarks` | 固定输入和环境的分段计时、内存、规模与吞吐，不做未经测量的加速承诺 |

整数、身份和离散状态原则上精确比较。浮点容差由指标/变换合同指定，不能用一个全局宽容差隐藏时间或业务差异。新语义实验与兼容差分分开报告。

## 首期明确不做

Web 产品、认证与数据库；分布式/GPU 仿真；JIT；自动修改运行中状态；完整 Project 编辑器；LLM 自创新 operation 并即时执行；先设计覆盖所有行业的大型通用语言。

## 当前下一步切片

Issue #4 的输入校验切片已实现：Python 与 Rust AOT 拒绝负工作时长、非法分钟类型/单位和未解析组件引用，保留合法输入 Plan；共享回归用例与旧缓存拒绝测试见[校验合同](strict-work-input-validation.md)。Issue #6 的当前版本基线测量入口见[整合基线](../benchmarks/integrated/README.md)。真实 Business/Core IR 主链及资源变化驱动候选派遣仍未实现。

## 后续工作

1. C1 的正式优化记录当前收录到 O6；O2a/O4b/compatibility lowering 已因收益不足回退，O7 在本机及 AMD128 独立复测后仍未达到收录门槛。MLIR 资源索引是独立 opt-in 试点，已证明 F35 九次执行下有 4.26% 总成本收益；推广前还要用另一台主机及更稠密、更多样的资源网络测量。完整共享 PreparedPlan 与 dense inventory/reservation 也应另行独立测量，分别单列 init/batch/RSS 或真实库存运输负载。
2. 将当前直接 lowering 拆成可持久化 Business IR 与 Core Simulation IR，补齐操作读写与唤醒依赖合同。
3. 增加 Plan schema 验证、缓存失效合同和更细的编译诊断；先把已通过实验门槛的 O5d guarded continuous advance 作为独立变更集成/验收，再在 O5 保守跳时基础上重新设计 transition-owned persistent event、owner generation、stale token 与 microstep convergence。当前尚未实现直接事件回调执行。
4. 扩展组织资源的多跳人员/设备运输与更多取消竞争案例。
