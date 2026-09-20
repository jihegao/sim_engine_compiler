# 合同目录规划

此目录尚无可执行 schema。下表是阶段 A/B 的合同清单，名称为本项目草案，不声称等于上游实际字段。先由小案例驱动 schema，再冻结版本；不复制一份新的 Project schema。

| 合同 | 内容 | 首次交付 |
|---|---|---|
| canonical input provenance | 上游提交、Adapter 版本、schema 身份、原始与规范输入 hash、导出方式 | A |
| semantic profile | 时间、作业策略、故障时钟、RNG、资源事务、指标口径 | A |
| Business IR / ModelRevision | 创作模式、领域版本、稳定 ID、实体关系、过程规则、参数、初始状态、来源 | B |
| Core IR | 有类型的状态/事件/表达式/操作、读写集合、时钟与采样请求 | B |
| Execution Plan | 格式版本、compiler/domain/profile 版本、backend ABI、操作能力、静态表、指令、状态布局 | B |
| RunRequest / RunResult | 模型/计划身份、参数、初始状态、seed、sample IDs、观测、horizon、结束原因及结果 | B |
| Diagnostics / SourceMap / Trace | 错误定位、反向业务 ID、规则/事件因果来源 | B |
| ModelPatch | base revision、变更、影响分析、新 revision 与验证证据 | D |

## 输入与输出身份

结构指纹包含规范化 IR、语义 profile、领域包及编译器版本、Plan ABI、编译选项、被固化参数和静态布局。运行指纹再包含参数、初始状态、seed/样本身份、horizon 和观测配置。执行证据额外记录运行时版本与平台信息。

规范化算法本身要版本化：规定键排序、数字表示、禁止非有限数、字符串编码与默认值处理；不能直接使用进程内 `hash()`。Project ID 不能替代内容指纹。标签或说明若不进入结构指纹，必须仍记录在修订身份与 source map 中。

参数声明标出结构参数、运行参数或元数据，以及单位、范围、默认来源和是否参与常量折叠。实体数量改变后必须重建相应布局/初始状态。缓存命中不表示 RunState 可复用。

## 操作能力

每个 operation 声明稳定名字与版本、输入输出类型、状态读写集合、资源/随机/时间副作用，以及 Python/Rust 支持状态。加载 Plan 时检查完整能力集合。未知 operation、profile 或 ABI 明确失败，不能跳过。

## 诊断与可解释性

诊断至少包含 `code`、严重度、阶段、消息、稳定实体/规则 ID、源字段路径与修复提示；区分已证明违反约束、可能风险和不支持能力。

Source map 同时连接原 canonical 字段、Business IR 节点、Core 操作和 Plan 指令/索引。关键 trace 包含 `event_id`、`cause_event_id`、`business_rule_id`、`process_instance_id`、`source_field_path`、`model_revision`、时间与排序键。

结果区分正常到达 horizon、完成、用户取消、预算耗尽和运行错误。未完工作、在途库存、有效预约与未释放资源按合同报告，不能把终止自动解释为业务完成。

## 待定项

- 上游 canonical schema 的实际版本与默认值行为。
- 兼容时间单位、phase 表与 horizon 边界。
- legacy RNG 的具体算法、分布变换及跨语言回放合同。
- Plan 的初期交换格式及 Rust ABI；首版优先可检查文件格式，性能布局由测量决定。
- JSON Schema 与 Python 类型的权威来源及同步检查方法；避免两份定义独立漂移。
