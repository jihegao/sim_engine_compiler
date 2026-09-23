# 观测隔离与 F35 热路径优化计划

状态：2026-09-21 已完成 O0、O1、O3、O4a、O6，以及显式 `event-time-v2` 的 O5 第一阶段。O5 以独立语义 profile 保留 canonical 15-phase 执行，在保守唤醒日历下跳过空分钟；F35 seeds `0/1/7` 的 full/summary 结果精确一致。O5b/O5c 不收录，O5d 仍是独立候选。O7 通过语义与目标 phase 验证，但本机与 AMD128 独立复测均未达到整体墙钟收录门槛。O2a、O4b 与 compatibility lowering 收益不足，均已回退。

优先顺序为：补齐测量保护 → 消除无效任务克隆 → 预计算静态关系 → 故障状态数组化 → 活动集合 → 有条件评估事件跳跃。前三个任务 phase 约占插桩执行时间的 79.7%，先处理其每分钟重复成本；保留 `full/summary` 观测隔离作为每轮优化的验收条件。

## 1. 现有证据与适用范围

本次检查的是以 `f59197cd884ef6514a2e212b79cd1b6118332211` 为 HEAD、包含尚未提交的观测隔离与剖析改动的工作树，不能仅用 HEAD 复现本文所读代码。原始 profile/观测报告没有记录构建提交，不能据此反推当时二进制的精确版本；下一轮必须补齐。

固定输入来自 [fixture manifest](../tests/fixtures/spare_mvp/f35-43day-5352a0d/manifest.json)：上游 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`，Plan 版本 `aircraft-support-plan/v1alpha2`，fingerprint `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。本地 Plan 为 9 架飞机、104 个任务、43 天/61,920 分钟、424 个组件定义、2 个资源节点；组件定义数不等于具有故障行为的组件数。

| 能力或结论 | 当前证据 | 本计划的解释 |
|---|---|---|
| 独立 Python/Rust runtime | B1/B2/B3 与 F35 seeds `0、1、7` 已有差分测试及报告 | 当前兼容范围的执行基线；并非所有模型已验收 |
| `full/summary` 观测隔离 | 三个 seed 的 RNG tape、metrics、终态、时间与停止原因比较 | 已实现；优化时继续保护，不能删 RNG tape 换取收益 |
| 未插桩执行时间 | seed 0，六组交错运行；full 中位 2.629 s，summary 中位 2.605 s；均值约 2.634/2.633 s | 没有稳定的执行加速证据 |
| 输出体积 | full 4,212,927 bytes；summary 1,392,096 bytes | 减少约 67%；序列化、绑定传输、RSS 的实际收益另测 |
| 内部 phase 计时 | full 五轮插桩中位执行 2.693 s | 用于定位，不能与正式未插桩墙钟混算加速比 |
| 事件跳跃、活动集合与新布局收益 | 尚无本项目优化前后对照 | 计划项，不能宣称已实现或已提速 |

直接 phase 中位累计时间为 preflight generation 724.2 ms、mission dispatch 712.7 ms、mission success 709.8 ms、failures 269.9 ms、resource dispatch 112.0 ms。前三项合计约 79.7%，加 failures 约 89.7%。

seed 0 的计数为 mission 扫描 19,319,040 项、job 扫描 49,410,043 项、component 扫描 19,275,687 项、preventive 扫描 8,813,646 项、Plan spec 克隆 19,778,872 次。Map 读/写计数约 3,958 万/1,927 万，是已插桩调用的下界；扫描次数也不能直接当作各项耗时比例。

`full` 事件 JSON 构造约 8.79 ms，占插桩执行约 0.33%；这个边界不覆盖调用 `emit` 前准备参数的克隆。火焰图中的 `String::clone`、`MissionSpec::clone` 和 `BTreeMap::insert` 均为 inclusive 样本，彼此重叠，不能相加。F35 seed 0 的 shipment 扫描计数为 0，运输与取消竞争必须用单独案例验收。

证据入口：[热路径报告](../benchmarks/hot_path/README.md)、[交错墙钟原始记录](../benchmarks/hot_path/results/f35-observation-interleaved-seed0-20260920.json)、[full profile](../benchmarks/hot_path/results/f35-seed0-full-20260920.json)、[summary profile](../benchmarks/hot_path/results/f35-seed0-summary-20260920.json)、[阶段 C 分段基准](../benchmarks/stage_c/README.md)。不同轮次、硬件或计时边界的秒数不直接相除。

## 2. 必须保持的语义与架构

- 保持 `legacy-minute-v1`、`legacy-sequential-v1` 和 `stable-topological-serial`。O1–O4 均保持分钟推进、phase 顺序和同阶段遍历顺序。
- 保持 Business IR → Core Simulation IR → Execution Plan 的分层方向。当前 Business/Core 尚未物化；本轮局部优化不另建 Project 解释器，也不以新索引代替三层 IR。
- 原 Plan 保持只读，派生静态索引可由一个只读 prepared-plan 对象共享；计时器、候选活动集合、预约和指标仍属于每样本 RunState。派生布局不是新业务真源。
- 稠密索引只用于访问；RNG 请求身份、业务 ID、source map、输入指纹和结果合同保持稳定。若将来持久化派生布局，须单独定义布局版本和缓存失效规则。
- 不改变 quantity 的抽样与最小寿命规则、故障传播阈值、资源候选顺序、分阶段预约、取消结算或串行作业策略。
- 领域规则继续由既有显式 operation/profile 表达，向 `domains/aircraft_support` 的边界演进；不得增加 `if domain == ...` 分支或在 IR 中执行任意表达式。
- 未知操作、profile、phase、单位/引用错误和能力缺口继续显式失败。不得用默认索引、空列表或跳过错误伪装兼容。
- 独立 Python reference 与固定旧模型 oracle 作为比较基线。不得同步修改两个后端的业务行为来使差分通过。

## 3. 工作包与推进顺序

每个工作包独立提交代码、语义证据与前后基准；前一项通过后再进入下一项。O4、O5 的投入由更新后的 profile 决定，避免按旧占比继续优化已不重要的路径。

| 工作包 | 范围与主要位置 | 风险 | 退出条件 |
|---|---|---|---|
| O0 测量保护 | `observation_benchmark`、`hot_path_profile`、差分测试 | 低 | 已实现并通过双观测级别、截断 horizon、批量/绑定差分；两二进制交错 runner 仍由外部执行 |
| O1 克隆消除 | `runtime.rs` 的三个 mission phase、`execute_minute` | 低，须差分证明 | 已实现并通过完整差分；任务扫描数不变，Plan spec clone 从 19,778,872 降至 459,832 |
| O2 静态关系预计算 | `plan.rs`、runtime 初始化、`matches_type`、`activity_for` | 低至中 | O2a preventive 索引已验证语义但未产生稳定收益，候选已回退；其他静态索引待独立证据 |
| O3 故障状态数组化 | `AircraftState`、故障初始化/推进/修复、终态转换 | 中 | 已实现、31 项差分通过并完成两轮复测；failures phase 由 265ms 降至 33ms |
| O4 活动集合 | job、mission、preventive、shipment 的候选与索引维护 | 中至高 | O4a waiting/running 集合已收录；O4b active-preflight 因整体收益不足已回退；其余集合等待有负载证据 |
| O5 事件跳跃评估 | Core 依赖/唤醒合同、调度器、timer token | 高，独立 semantic profile | O5a 已收录；O5b 拒绝、O5c 不收录、O5d guarded candidate 通过实验门槛但待独立集成；持久 callback 仍未实现 |
| O6 compiled steps | activity/step 派发字段、静态 spare requirement、batch 共享 layout | 中 | 已收录；31 项差分通过，24/24 固定二进制单元正向，跨会话中位改善 11.09%–18.17% |
| O7 dispatch clone elision | waiting 排序键、route scan、step code 的 owned clone 下沉 | 低至中 | 候选；31 项差分和目标 phase 通过，但 AMD128 六组固定 CPU 复测中 seed 7 未稳定同向，所有单元均低于 5%，暂不收录 |

### O0：补齐测量与观测保护

1. 先将现有观测隔离与剖析改动固定为独立基线提交，或保存可恢复的源码清单与完整差异（包括未跟踪文件），再生成优化候选。基准记录源码提交、工作树差异摘要、二进制摘要、Rust/toolchain/锁文件、构建 features、主机/OS/CPU/线程数，以及 Plan fingerprint、seed、观测级别、预热/重复次数、运行顺序与计时边界。原报告保留不覆盖。
2. `hot_path_profile` 当前只比较插桩与未插桩的 RNG/metrics/终态哈希。补上 `full` 的完整 trace、`time`、`stop_reason`、身份元数据比较；`summary` 同样比较非 trace 字段并断言 trace 为空。
3. 扩展现有隔离测试到 B1/B2/B3、F35、截断 horizon、批量/绑定路径。保持 `full` 为兼容默认值；summary 仍执行相同业务和 RNG，只有 trace materialization 不同。
4. 为 profile 补充按 phase/调用点区分的 clone 计数、候选访问数与峰值活动集合长度。既有总计数保留可比口径，新增计数注明覆盖范围；没有分配器测量时不得把 clone 次数称为分配次数。

产物：测量工具与验收测试、带版本的前后基准目录。O0 本身不要求提速。

### O1：先消除逐分钟任务定义克隆

定位函数：`phase_create_preflight`、`phase_dispatch_missions`、`phase_mission_success`。当前都在筛选条件前执行 `self.plan.missions[mission_index].clone()`，对应 `61,920 × 104 × 3 = 19,319,040` 次深克隆，占已记录 spec 克隆约 97.7%。这不代表有同等比例的耗时可被消除。

- 先用任务状态及只读标量判断是否需要处理。通过缩小借用范围、拆分只读 Plan 和可变状态访问，读取所需字段；字符串仅在实际业务写入或输出需要拥有它时复制。不得将深克隆替换成每个扫描项一次 `Arc::clone`。
- 保持原 Plan 任务顺序。此切片仍逐分钟扫描全部任务，单独验证克隆消除的效果，不同时引入任务队列。
- `execute_minute` 的 phase 列表当前每分钟克隆，再逐项复制字符串。可将已校验 phase 转为只读 ID 序列，日志输出时映射原名称；严格保留顺序、重复阶段行为及未知 phase 错误。
- 调用点为 trace 预构造的字符串可顺带延迟到确需输出时，但不把这项当作主要收益来源，不新增观测模式。

验收：三个 mission phase 的无条件深克隆归零，其他事件必要克隆单列；seed 0 分钟循环仍为 61,920、三个 phase 合计扫描仍为 19,319,040；按完整结果差分确认业务路径未变，再重测 phase 与未插桩墙钟。

### O2：静态关系与候选索引

复用现有 `activity_by_group_phase`、`children_by_component`、`failure_components_by_aircraft`，避免再建一组语义不同的查找逻辑。候选方向如下：

- 预计算 mission 对 aircraft 的类型匹配结果，保留空类型通配与现有 token 规则；运行时继续判断 availability、预约和准备状态，不能预选最终派遣飞机。
- 预计算 group/phase/aircraft 的兼容 activity 候选，保留必须唯一的校验；不可达组合不凭空选一个默认 activity，预计算不得掩盖原有歧义/缺失错误。
- 按 aircraft 索引 preventive cycles、故障组件与树邻接关系，维持原 Plan 次序。预计算任务成功点的静态 duration offset，实际起点仍按运行态决定。
- 资源节点索引已经存在；只消除仍在重复的匹配和静态 step requirement 构造。动态注入备件、`non_replacement`、预约、库存及路线容量继续现场计算；保留现有重复产品项处理语义，不借优化重新解释数量。
- 静态索引共享给批量样本；一次性构建成本单列，计入加载准备与端到端，不能移出执行计时后不报告。

验收：类型通配/多 token、候选顺序、零/多个 activity 匹配、多个 preventive 同时到期均有测试；静态索引与直接筛选逐项一致，Plan 指纹与业务身份保持不变。O2 不引入持久化缓存。

### O3：故障剩余寿命改为索引状态

目标是 `failure_remaining` 和 `component_failure_minutes` 的热路径访问。优先使用每 aircraft 的适用组件槽位与显式缺失状态，例如 `Option<f64>` / `Option<i64>`；不要以 0 表示未初始化，也不要默认分配全部 aircraft × 全组件的巨大矩阵。

- prepared plan 保存槽位到原 component index/ID 的映射；每样本只持有可变值。不同飞机共享产品定义时仍有独立故障状态。
- 初始化仍按原 aircraft/component 顺序执行“先抽样、后适用性判断”。不得因有适用组件索引而跳过原来会消耗 RNG 的不适用组件。
- countdown 保持每次 `remaining -= 1.0`，保持 missing-timer、维修完成重采样和 quantity 循环的调用顺序。改为累计暴露量或直接算故障时间属于后续语义敏感优化。
- 保持同分钟组件遍历、故障树传播和提前返航后 `break` 的行为。缺失、已故障、已修复状态不得合并。
- 输出时恢复现有业务键与顺序，source path 不变。组件树集合优化仅在重测后仍有成本时追加，不与数组迁移捆绑。

验收：故障 countdown 的树 Map 读写归零，适用组件访问顺序不变；当前定向测试已覆盖两机共享组件状态隔离、quantity > 1、不适用组件仍抽样、missing timer 和业务键恢复，既有 B2/F35 差分覆盖维修与完整轨迹。地面暂停/恢复、同分钟多故障及传播阈值仍需在后续扩展 fixture 中加强。静态 slot→component 列表当前仍由每个 Runtime 构建；共享 prepared layout 与初始化/内存分段测量归入后续 O2，不把本轮执行计时外的收益计入 O3。

### O4：减少历史与不相关实体扫描

拆成两个可独立回退的切片，保持分钟与 phase 调用不变：

1. **作业集合**：维护 waiting、running、按 mission 的活动 preflight、按 aircraft 的 preventive、待归还预约和在途 shipment 索引。历史 jobs 保留在结果存储中，离开调度扫描。创建、启动、完成、取消、运输到达与预约返还必须更新所有相关索引。
2. **任务集合**：按 preparation/start 等时间门槛维护候选集合，另维护未完成成功点评估的集合。到期任务激活后仍按原 Plan 顺序执行，不改为按时间堆弹出顺序争抢飞机。

必须保留以下容易被优化改变的细节：

- waiting job 排序键是 `(activity.priority, started_time.unwrap_or(current_minute), job_id)`。最后一项是字符串次序；不能替换成创建序号，未启动作业的第二项也不是固定值。
- `phase_mission_success` 使用 `actual_start.unwrap_or(planned_start)`，即使未起飞或已取消也可能产生失败事件。不能只维护飞行中任务；先到成功点、后可能延迟起飞的轨迹也必须照旧。
- mission dispatch 先尝试满足派遣条件，再判断取消门槛；同分钟刚好可派遣时不能先取消。
- `cancel_mission_preflight` 标记取消，保留的备件预约由后续 `transport_arrivals` 处理。不得提前返还以改变本分钟后续任务可见库存。
- preventive 同时满足多个周期时按现有顺序选择首个；同分钟新建作业能否被后续 phase 看到、零时长步骤何时完成均按参考 trace 保留。

验收：用调试断言将维护集合与当时直接筛选结果比较；增加“相同活动作业、增加已完成历史作业”的扩展案例，证明访问计数随活动量变化而非历史量。合成规模案例标明来源，不称为 F35 上游复现。

执行结果：O4a 只维护 waiting/running job index，保留 waiting 三键排序与 running 的 job-index 顺序；空步骤、同分钟重新分派、取消释放和下一分钟预约返还均有定向回归。seed 0 的 waiting/running 实际候选访问为 150,975/90,839，峰值为 7/8。四组同会话固定二进制对照中 24 个单元有 23 个正向，各 seed/观测组合的跨会话中位改善为 5.20%–6.76%，证据见 [O4a 报告](../benchmarks/hot_path/results/20260920-o4a-1f394ba/README.md)。收益主要来自 job progress；resource dispatch phase 只呈小幅趋势，仍是主要热点。

O4b 按 mission 维护 active-preflight job index，将 seed 0 的旧历史暴露估计 7,214,145 项降为 25,700 次候选访问，preflight phase 约减少 4–5ms；两轮整体墙钟却只有约 0%–2.5% 变化，未达到约 5% 收录线，候选已回退，证据见 [O4b 未收录报告](../benchmarks/hot_path/results/20260920-o4b-838e6bc/README.md)。preventive、取消预约与 shipment 索引没有继续叠加：前者已有 O2a 的负结果，后两者在固定 F35 运行中没有正路径负载。任务时间集合因 success-point fallback、派遣后取消等语义风险单独保留，不借 O4 名义顺带实现。

### O6：resource dispatch compiled steps

Runtime 从只读 Execution Plan 派生 activity/step layout，预存资源节点、priority、duration、人员/设备需求、step code 与规范化静态备件。`resource_dispatch` 不再为每次候选深拷贝完整 `ActivitySpec` 和 `WorkStepSpec`；`job_progress` 与取消释放复用同一 layout。静态 spare 继续保持原先临时 `BTreeMap` 的排序与重复键覆盖语义，动态 replacement spare 只在最终步骤按原规则合并，`non_replacement` 仍清空需求。批量 samples 共享 prepared activity layout，但其他 Runtime 静态索引仍按 sample 构造，不能据此宣称完整 `PreparedPlan` 已完成。

定向测试覆盖静态 spare 重复键、动态注入及 non-replacement；完整 31 项差分继续通过。四组固定二进制对照 24/24 单元正向，各 seed/观测组合跨会话中位改善为 11.09%–18.17%；seed 0 插桩 resource dispatch 中位由 full/summary 105.474/101.336ms 降至 64.735/60.875ms。证据见 [O6 报告](../benchmarks/hot_path/results/20260920-o6-4508860/README.md)。固定 F35 step 没有静态 spare，因此本轮不能量化 dense inventory 或复杂运输场景收益。

### O7：resource dispatch 重试路径克隆消除

waiting job 的三键顺序保持不变，但排序比较器借用 job ID；supply route 仍按 Plan 顺序每分钟
重试，但只借用 route spec/复制标量，实际发运时才复制 trace 字符串；step code 只在作业真正
启动时复制。没有缓存无库存结果，不改变后续库存到达或取消返还后的可见性。

新增 `supply_route_candidate_visits` 证明 seed 0 的 148,721 次 route 访问仍然发生，而 Plan spec
clone 从 153,010 降至 4,289。resource dispatch phase 的 full/summary 五次中位由
63.249/59.389ms 降至 45.643/40.854ms。四组 fixed-binary 对照 24/24 单元正向，跨会话中位
改善为 3.73%–11.06%；单/三线程 Stage C batch 与 end-to-end 也同向改善且结果 hash 不变。
seed 7 约 3.7% 的首轮收益低于 5%；本机独立重建复测中多个 seed/观测单元转负，且绝对时间随
运行顺序大幅漂移。AMD128 随后以固定 CPU、双 block 预热和正反各三组复测：seed 0/1 六组均
正向但跨 session 中位仅 2.45%–3.26%，seed 7 full/summary 仅 5/6 和 4/6 正向，中位仅
0.48% / 0.80%。按统一门槛 O7 暂不收录，代码只作为未提交 candidate。
证据见 [O7 报告](../benchmarks/hot_path/results/20260920-o7-dispatch-clone-elision/README.md)。

O7 前曾独立测试 compatibility lowering，四组单元变化为 -0.69%–2.84%，未达到收录线且包含
负单元，已完整回退。共享其他 prepared indexes 仍属于初始化/批量/RSS 实验，不能混入 execution
计时结论。

### O5：条件式推进事件跳跃

只有 O1–O4 后的 profile 仍显示分钟空转占主导才进入。先补 Core 操作读写集合、guard 依赖、时间唤醒与 phase 可见性合同；证明可跳过的区间内不会改变任何 guard、指标或随机请求。

唤醒来源至少包括：准备/起飞/取消/成功点、返航、作业完成、资源释放、运输到达、取消后的预约返还、日历跨日、preventive 阈值、飞行暴露故障、requested horizon 与最终 cutoff。过期或已取消事件必须有 owner generation / timer token，不能复活作业或重复结算。

尤其不能把逐分钟浮点减法未经证明地改为一次减去跨度。等价无法证明时保留兼容分钟路径；新 `event-time-v2` 或 RNG/并行策略应作为独立语义版本立项，不计为当前兼容优化。

执行结果：O5 第一阶段新增显式 `event-time-v2`，只在 canonical phase 表下启用。运行时从运输、返航、作业完成、故障暴露、跨日、preventive、任务准备/派遣/成功点、延迟可见性和 horizon 推导下一唤醒分钟；区间内按 legacy 顺序推进连续倒计时，唤醒分钟仍执行完整 phase 表。F35 seed 0 从 61,920 个分钟迭代降为 1,609 个唤醒，跳过 60,311 分钟。B1/B3/B2、两个漏唤醒回归、F35 三 seed 双观测和 184 组参数网格均未出现除 Plan identity 外的差异。AMD128 两个稳定会话的各组合改善为 69.74%–81.62%，证据见 [O5 报告](../benchmarks/hot_path/results/o5-event-time-v2-20260921/README.md)。

边界：当前已接受的 O5a 每次 wake 都重建临时日历，仍逐分钟扣减 running job/故障时钟，并在目标分钟执行全 phase 表；没有持久 heap、owner generation、stale token 或 microstep callback。因此它是兼容结果导向的保守 time skipping，不把 O5 标为完整离散事件回调能力。

O5b/O5c/O5d 的 AMD128 后续实验已经完成。O5b 复用持久 heap、owner generation 与 lazy invalidation，但每次 wake 仍扫描状态并用 `BTreeMap` 协调目标集合；六格跨会话中位改善为 -56.03% 至 -72.65%，候选拒绝。O5c 从最早保守 phase rank 开始执行 canonical minute table，18 个 session/cell 均正向，但只有 0.71%–1.58%，低于约 5% 收录线。O5d 对 job `i64` 使用 checked subtraction，对 failure `f64` 仅在有限、正值、`<= 2^53` 且不跨 due tick 时一次减去跨度，其余保留逐 tick fallback；三轮 108/108 measured pairs 精确等价，六格改善 30.61%–41.16%，最大相对 MAD 1.063%。O5d 通过候选门槛，但本轮没有把它与 O5a 合并；源差异、守卫实验和原始计时见 [O5b/O5c/O5d 报告](../benchmarks/hot_path/results/20260921-o5b-o5c-o5d-amd128/README.md)。真正的 O5b 后继若重做，应把 schedule/cancel 放到状态变化点，而不是重复当前协调扫描。

## 4. 统一验收门槛

### 语义门槛，先于性能

| 检查面 | 必须通过 |
|---|---|
| 固定真实案例 | F35 seeds `0、1、7`：旧 oracle → 独立 Python → Rust；full 比较 RNG、完整业务 trace、metrics、终态/资源账本、时间、停止原因与身份 |
| 观测与插桩 | full/summary 非 trace 字段一致，summary trace 为空；插桩开关不得改变 full 完整结果 |
| 并行与绑定 | seeds `[7,0,7,1]`、1/3 线程、两个观测级别；重复 seed 保留独立 sample_index，逐样本等价；Python 绑定使用本次新构建，测试不可因未安装而跳过 |
| 手算边界 | B1/B2/B3，加每个切片的目标回归；同分钟返航/完成/故障/派遣、取消后归还、跨日、零时长、horizon 前/恰好/后均覆盖 |
| 失败路径 | 未支持 operation/profile/phase、无效引用/单位、能力缺口继续显式拒绝；索引化不把错误变成默认成功 |
| 状态不变量 | 人员/设备容量、库存与在途量、预约一次结算、作业终态、样本间状态隔离 |

F35 三个 seed 不是所有模型的证明。Rust 现有 synthetic 差分只覆盖保存的四个主案例；reference 中额外的横向补给、取消预约等测试不能自动视为 Rust 也通过，受影响案例须加入 Rust 差分。

沿用现有差分工具：身份、顺序、整数时间与离散状态精确比较；浮点仅使用已有变换/指标容差（当前 F35 差分为 `rel=2e-15, abs=1e-12`），不得扩大容差隐藏事件分钟或抽样次序变化。同平台优化前后优先要求结果精确一致。

实施时基础命令：

```bash
cargo test --manifest-path rust/runtime/Cargo.toml
uv pip install --python .venv/bin/python -e .
.venv/bin/python -m unittest discover -s tests -v
```

这是后续实施门槛；本次文档修改没有运行上述仿真验收命令。

### 性能门槛与报告口径

1. 同一主机、相同固定 Plan、相同 release 配置，基线/候选分别构建并保留二进制摘要。正式计时不启用 `profiling` feature 或内部插桩，系统采样单独构建、单独运行，不并发执行其他基准。
2. F35 seeds `0、1、7`，full/summary 分开报告；每个组合预热至少 1 次，至少 6 组基线/候选交错执行，轮换先后次序。保存全部记录，报告每 seed 中位数、均值、范围及配对耗时比，不仅报告汇总或最快一次。
3. `execution` 保持现有外部 `runtime.run(...)` 边界，包括结果构造；内部 `profile.execution_ns` 只覆盖分钟循环，另列。完整分段须涵盖 canonical→Plan 编译、读取/解析/校验/指纹、静态索引准备、RunState 初始化及初始 RNG、执行、序列化、写出、Python 调用和端到端。区分重叠边界，不把 Python 调用时间再次叠加进端到端。
4. 对输出优化另外测 full/summary 的序列化、绑定调用、字节数与内存；对批量测 1/3 线程吞吐。不能把 summary 的体积收益当作 Rust 执行收益，也不能将旧阶段 C 的 3.060 s 与本轮 2.629 s 直接相除。
5. 内存以新进程区分 Plan、单 RunState、执行峰值和保留结果；同时记录状态布局大小与结果大小。旧进程峰值 RSS 包含多份结果，不能当作每样本内存。新增矩阵或缓存若使内存变差，必须明确收益与代价。
6. 建议的工程收录线为：在第二个独立会话中复现收益，且收益超过同场基线波动。小于约 5% 的改善默认不称为明确提速，除非追加证据能分辨；任一 seed/观测级别或端到端持续回退超过约 5% 时先定位再决定。**5% 是待采用的筛选规则，不是测得的噪声上限或加速承诺。**
7. 差分不通过则停止该切片并定位首处分歧，不能靠更新 golden 接受结果。没有可重复收益的复杂改动不进入后续叠加；纯结构整理若保留，应单独说明其价值和测量结果。

每轮产物保存到 `benchmarks/hot_path/results/<日期>-<工作包>-<提交>/`，包含 manifest、语义验收摘要、未插桩前后原始记录、profile/火焰图和简短结论；源 fixture/oracle 留在原目录。结论分别列出“实现了什么、哪些案例已验证、测得什么、哪些仍未验证”。

## 5. 首轮交付与后续决策

本轮在原 O0/O1/O3/O4a/O6 工作上整合了 O5 第一阶段及 O5b/O5c/O5d 实验记录；原固定源版本的 41 项 Python/Rust conformance 与 differential tests、O5 的 184 组参数网格差分和 AMD128 交错复测有各自报告。本次从最新 main 起的整合回归单独记录，不把既有数字当成本分支的验收结果。O1 消除 19,319,040 次 mission spec 深克隆；O3 将故障热状态改为稀疏数组；O4a 将 waiting/running 历史扫描移出两个目标 phase；O6 将 resource dispatch 的 activity/step 解释与深拷贝移到 prepared layout。O2a、O4b、O5b 与 O5c 均因整体收益不足或回退而不收录；O5d 保留为待独立集成候选。O7 未达到整体墙钟门槛，暂不收录。O5 的 persistent callback 与 microstep convergence 尚未实现。

当前不设“达到某倍加速”承诺。也不因本轮计划新增 UI、服务器、数据库、分布式调度、JIT、运行中编辑或 DAG 并行策略。Business/Core IR 物化与持久化缓存仍按架构路线推进；局部布局优化不意味着这些能力已经完成。
