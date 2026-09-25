# Canonical work input validation

Issue #4 的第一切片。Python canonical 编译器与 Rust AOT 在创建 Plan 前检查以下字段；MLIR 编译入口复用 Python 校验，MC 入口复用 Rust AOT 校验。此处没有改变 Project JSON 或上游 Adapter，也不宣称已经完成所有 canonical schema 校验。

| 字段 | 接受规则 | 错误 |
|---|---|---|
| `support_activities.activities[i].duration_minutes` | 缺省/null 保留默认值；有限、非负数值 | `negative_duration`、`invalid_duration_type`、`duration_out_of_range` |
| `.jobs[j].durationMinutes` / `.duration_minutes` | 同上；两个别名均检查，即使另一个具有优先权 | 同上 |
| `.equipment_id` | 缺省/null/空字符串表示通用活动；其他值必须为已声明组件的字符串 ID | `unresolved_component_reference` |

为保持已有兼容规则，纯 JSON 数字字符串（允许外围空白）显式归一化为分钟数；不解析 `3 hours`、`3分钟` 等单位文本。布尔值、空字符串、数组、对象、NaN、Infinity 被拒绝。支持的时长范围为 `[0, 2^63)`，有限小数沿用向零截断；截断后为零沿用旧默认值，**不引入瞬时作业语义**。活动缺省时长为 30 分钟，步骤缺省取活动时长。负数不能因截断或默认值规则而被接受。

Python `CompilationError` 保留原有导入入口，并为这些校验提供 `code`、`source_path`、`message`。Rust 使用可 downcast 的 `CompilationDiagnostic`；CLI/MC 的错误文字含相同 code 和字段路径。其他既有诊断尚未统一迁移到这个结构。

`aircraft-support-aot/v1alpha3` 使所有旧版本编译缓存失效，包括 pre-Adapter Project 缓存；缓存格式仍为 v3，Plan 格式和合法输入 Plan 指纹不变。MC 遇到一个非法输入组时，仅该组在 compile 阶段失败，其余合法样本仍执行。旧版本 envelope 即使被放到新文件名，也不能绕过版本检查。

共享案例表 `tests/fixtures/synthetic/work-input-validation.json` 由 Python/Rust 同时消费，覆盖两个时间 profile。另有五个固定 Plan 的精确比较、有效组件绑定、旧缓存绕过反例和 Python MC 错误透传测试。F35 固定输入仍绑定 manifest 中的上游 revision `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` 和 canonical hash `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`；不读取活动数据库。
