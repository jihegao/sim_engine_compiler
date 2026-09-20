# Aircraft support domain

首个领域包，尚未实现。计划按实体、规则与 lowering 分工：

- `model.py`：任务模板/实例/名额、飞机、产品/组件位置/实例、保障模板、节点与资源。
- `validation.py`：领域约束、适用关系、局部 DAG、故障树及可证明的不可满足条件。
- `lowering.py`：将领域对象与规则变为 Core 操作；编译静态候选集合，保留运行时选择。
- `operations.py`：显式版本化的领域操作语义与后端能力要求。
- `metrics.py`：业务可用谓词、出动/中止、延误、停机归因及分母定义。

canonical 传输格式由 integration 解包后进入领域构建逻辑，不在此重建 Project JSON 解释器。旧模型的 daily-v1、quantity、稳定串行和组织分配规则须先有基线证据。

原生事件时间或 DAG 并行规则采用不同 profile。领域包不能偷偷改变兼容语义以取得性能收益。
