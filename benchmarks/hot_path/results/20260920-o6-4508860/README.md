# O6 候选：resource dispatch compiled steps

候选源码提交：`4508860725bcc9d3511d3d90a0cb817fc8553d00`。固定对照为回退 O4b 后的
`0d13ca7`；其 runtime 源码束 SHA-256 为
`6ae3b92e26f5a57bb7792181b1a50e24cab1bb4fe970ce6760d3976bcf22c208`，与已收录 O4a
报告中的源码束一致。候选源码束为
`ea87511ca8245ea140af2568a9788d07a1ca302ca7ad6473ddd438e7a1864b03`。固定 Plan
fingerprint 为 `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。

## 实现与语义边界

- Runtime 初始化时将 activity/step 的 dispatch 字段编译为只读 prepared layout：资源节点、
  priority、duration、人员/设备需求、step code 和规范化静态备件。
- `resource_dispatch` 不再为每次 waiting candidate 深拷贝 `ActivitySpec` / `WorkStepSpec`，
  `job_progress` 与取消释放也复用相同 layout。静态备件保持原 `BTreeMap` 语义：产品键排序，
  重复键保留最后数量；只有末步动态注入 replacement spare 时才构造临时合并表。
- prepared layout 是 Execution Plan 的派生只读表示，不改变 Plan JSON、fingerprint、业务身份或
  RunState。批量执行在 samples 间共享该 layout；其他静态索引仍按 sample 构造，未宣称已经完成
  全量 `PreparedPlan`。
- waiting 排序仍是 `(activity.priority, started_time.unwrap_or(current_minute), job_id)`；库存、
  分阶段预约、运输、维护方法、串行步骤和 RNG 调用顺序未改变。

新增定向测试覆盖静态 spare 的排序/重复键语义、动态 replacement 注入相加，以及
`non_replacement` 清空需求。Rust 13 项单元测试与 3 项 profile 工具测试、clippy，以及重建
PyO3 binding 后的 31 项 Python/reference/Rust conformance 与 differential tests 全部通过。
F35 seeds `0、1、7` 的完整 trace、RNG、metrics、终态、时间与停止原因保持一致；两个观测级别、
截断 horizon 及 `[7,0,7,1]` 的 1/3 线程批量路径也在覆盖内。

## 固定二进制同会话对照

每个单元各执行 6 次并取中位数。四组会话 A/C 先运行 O4a，B/D 先运行 O6；正值表示 O6
更快。24 个会话单元全部为正。

| 会话 | seed 0 full | seed 0 summary | seed 1 full | seed 1 summary | seed 7 full | seed 7 summary |
|---|---:|---:|---:|---:|---:|---:|
| A | 17.76% | 18.64% | 17.35% | 18.26% | 11.36% | 12.41% |
| B | 17.91% | 18.12% | 18.12% | 18.83% | 12.77% | 13.56% |
| C | 17.40% | 17.89% | 16.84% | 17.32% | 10.82% | 12.59% |
| D | 17.89% | 18.22% | 17.11% | 17.87% | 10.82% | 12.14% |
| 跨会话中位 | **17.82%** | **18.17%** | **17.23%** | **18.06%** | **11.09%** | **12.50%** |

基线与候选在所有 paired 报告中的逐 seed/观测 `result_sha256` 精确相同。seed 0 full 的
结果 SHA-256 继续为
`aa6e7ca01d2cb4044e1664a4ab27f476f0f4d1aefcefde93bdca1cc1f5d5f4d2`。

## 热路径变化

下表为同次工作会话各 5 次 seed 0 profile 的中位数；插桩和未插桩边界不混算。

| 观测 | 指标 | O4a | O6 |
|---|---|---:|---:|
| full | 未插桩 execution | 238.581 ms | 195.772 ms |
| full | 插桩分钟循环 | 284.091 ms | 242.750 ms |
| full | resource dispatch | 105.474 ms | 64.735 ms |
| full | job progress | 9.053 ms | 6.441 ms |
| summary | 未插桩 execution | 227.417 ms | 185.731 ms |
| summary | 插桩分钟循环 | 272.728 ms | 230.534 ms |
| summary | resource dispatch | 101.336 ms | 60.875 ms |
| summary | job progress | 5.385 ms | 2.778 ms |
| full/summary | Plan spec clone 计数 | 459,832 | 153,010 |

因此本轮收录结论是：编译 step layout 将首要热点 `resource_dispatch` 降低约 39%–40%，并使
F35 单样本执行在四组固定二进制对照中的跨会话中位改善达到 11.09%–18.17%。这只证明当前
固定 F35 43 天案例和已验收 synthetic 范围；F35 的 step 没有静态 spare 正路径，因此不能用
该性能数字量化 dense inventory 或复杂运输负载的收益。

## 未完成项

- inventory / reservation 仍使用字符串键 Map；本轮只预编译 step 与静态 spare requirement。
- mission/aircraft/activity compatibility 尚未 lowering 为稠密候选关系。
- prepared activity layout 已在 batch samples 间共享，但 failure/component/activity lookup 等
  其他派生索引仍按 sample 构造；未做 compile/init/batch throughput 与内存分段基准。
- waiting jobs 仍每分钟构造 Vec、按三键排序并克隆排序用 job ID；峰值只有 7，须单独验证收益。
- event-time V2、时间跳跃和运行世界热编辑均未实现。

## 文件

- `paired-{a,b,c,d}-{o4a,o6}.json`：四组固定二进制对照原始记录。
- `f35-observation-interleaved-seeds-0-1-7.json`：候选独立复测。
- `baseline-o4a-seed0-{full,summary}-profile.json` 与
  `f35-seed0-{full,summary}-profile.json`：前后插桩/未插桩 profile。
- `host-manifest.json`：主机、工具链、候选与基线身份说明。

基线二进制是在干净 `0d13ca7` 工作树构建并在代码修改前保存；该旧二进制没有设置编译期
revision 标签，因此 paired JSON 中 `source_revision` 为 `null`，但仍记录了独立 executable
和内嵌 source-bundle SHA-256。候选报告记录完整提交、`clean_at_commit`、二进制与源码束摘要。
