# 实施路线与验收

当前已完成项目结构、F35 上游基准、Independent SimPy Reference Runtime Conformance，以及阶段 C 的独立 Rust 单样本与批量执行内核、稳定排序、Python 绑定和正式分段基准。详细证据见 [独立 reference conformance](b1-independent-reference.md)与[阶段 C 基准](../benchmarks/stage_c/README.md)。B1/B2/B3 兼容范围及 F35 seeds `0、1、7` 已完成 Python/Rust 完整结果差分；阶段 B 后续是物化 Business/Core IR，阶段 C 后续是缓存失效合同与有证据支持的事件跳跃。

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

### C1：基于 F35 热路径的兼容优化（O0/O1 已验收）

执行顺序与逐项验收见 [观测隔离与 F35 热路径优化计划](performance-optimization-plan.md)。
先补齐测量保护、消除三个 mission phase 的无效深克隆，再预计算静态关系、迁移故障状态数组，
随后按新 profile 评估活动集合。事件跳跃须等待完整唤醒合同与边界差分，不作为首轮改动。
O0 已补齐构建/源码身份、插桩等价和双观测级别测试；O1 已移除三个 mission phase 的逐项深克隆及逐分钟 phase 表复制。31 项测试通过，F35 seeds `0、1、7`、截断 horizon、重复 seed 与 1/3 线程均已差分。两轮候选复测已完成，更新后的主要成本为 failures 与 resource dispatch；证据见 [O1 候选报告](../benchmarks/hot_path/results/20260920-o1-50857fe/README.md)。

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

## 后续工作

1. 按 C1 推进 O3 故障状态数组化；完成差分与复测后，再依据剩余调用点决定 O2 静态关系预计算范围。
2. 将当前直接 lowering 拆成可持久化 Business IR 与 Core Simulation IR，补齐操作读写与唤醒依赖合同。
3. 增加 Plan schema 验证、缓存失效合同和更细的编译诊断；具备依赖合同后单独评估兼容事件跳跃。
4. 扩展组织资源的多跳人员/设备运输与更多取消竞争案例。
