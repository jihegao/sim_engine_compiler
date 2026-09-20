# IR

阶段 B 逐步增加以下类型模块，目前尚无实现：

| 计划模块 | 职责 |
|---|---|
| `business.py` | BusinessModel、ModelRevision、实体关系、规则 AST、过程模板 |
| `core.py` | 类型化状态、事件、guard/effect、事务、时钟、采样、指标 |
| `plan.py` | ExecutionPlan、静态表、指令块、索引、状态布局、能力需求 |
| `profiles.py` | 版本化时间、RNG、作业与资源语义引用 |
| `provenance.py` | 输入身份、编译身份、修订来源与 SourceMap |

IR 不持有运行中的飞机状态、预约账本、事件堆或 RNG 实例。源字段路径和稳定业务 ID 保留到 Plan；稠密索引只是执行优化，不是业务身份。

合同清单见仓库根目录 `contracts/README.md`。在 schema/类型权威来源确定前，不增加“任意 dict 都合法”的宽松 schema。
