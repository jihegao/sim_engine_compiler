# J35 ENLOG → Execution Plan 事件映射（候选，2026-09-26）

本文件是 4700-3 Codex 原始 `evidence/event-mapping.md` 的仓库副本。下文相对证据文件名位于 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\`；完整验收结论见[本机报告](j35-event-parity-4700-3.md)。

## 证据与解释规则

- 固定 Plan：[`execution-plan.json`](../../tests/fixtures/spare_mvp/j35-amd128-0e709bd/execution-plan.json)，字节 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，Plan 指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`。
- 原生首样本日志：`raw/j35-page-enlog-probe.log`，SHA-256 `6fca1d0cbd1c75b7a8957c2fc364b7f4e784418c411f24d5fde02e59b84942b3`。`enlog-probe-diff.json` 核对原候选与日志探针 JSON 仅 `Control.ENLOG=N→Y`。
- 手册 `C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf` 印刷页 233 明确 ENLOG 只将**首个重复样本**的完整调试日志写为输入同名 `.LOG`；`manual-enlog-search.json` 保留读取结果。ENLOG 会改变运行开销，正式性能运行必须关闭。
- `Time:` 为 SIMLOX 的小时打印值；乘 60 可得**由打印值推算**的分钟。日志小数位可变，不能当作精确内部时间或同刻微步序号。首波确定性工序比较使用 ±0.001 分钟的打印容差；随机故障不做这一容差下的等价断言。
- 原生 `<BM-J35-43D,J35_UNIT,0,0,n>` 的 `n` 与 Plan `missions[n]` 是**候选序位映射**：104 条原生创建时刻均等于对应 Plan 的 `preparation_start`。原生 `<J35,n>` 与尾号 `J35-(n+1)` 只由首波选机顺序推断；原生聚合部署没有逐机尾号和初始寿命，不能当稳定跨引擎身份。行号仅作原始日志定位。

| 语义类 | SIMLOX ENLOG 字段与单位 | Plan / Rust 字段 | 已核对范围、首个差异或限制 |
| --- | --- | --- | --- |
| 通知与准备 | `mission created` 原生任务序位、`Time` 小时；`preparation started/ended` 原生机序位；`subtask … seqno`、起止时刻 | `missions[n].preparation_start`；`preflight_created/completed`；`operations_step_started/completed.details.step_index` | 104/104 创建时刻配对。受控通用资源模型中，首波两机 14 道工序共 56 个起止时刻均在打印容差内配对，见 `first-preflight-control-comparison.json`。未证明所有机的稳定身份与全部同刻顺序。 |
| 起飞、取消与结果 | `mission starting`、`mission cancelled`、`mission success`、`mission completed`；时刻小时、任务原生序位、参飞机序位 | `mission_launched`、`mission_cancelled`、`mission_success_point_*`、`mission_returned`；分钟、稳定任务 ID / 尾号 | 原生开始 92 波，Rust 89；原生成功日志 79 波，Rust 82。候选配对的首个成功结果差异为序位 2：两边第 600 分钟起飞，原生第约 628.602 分钟因故障中止，Rust 于第 843 分钟通过成功点。首个起飞有无差异在序位 19（原生第 10740 分钟起飞、Rust 取消）。原生 `mission success` 在完结时记日志，不能当 Rust 0.75 成功点事件。 |
| 故障 | `critical random failure added` 的 `Time`、`<J35,n>`；后续缩进行中的 `subitem failed:<J35-PART-…>` 与复杂度 | `component_failed` 的分钟、尾号、`component_id`、`source_path`；`sample_requests` 另记随机请求 | 原生 19 次关键故障，首个约第 628.602 分钟，为 `<J35,5>` 上部件 `…0799`；Rust 10 次组件故障，首个第 3611 分钟，为 `J35-05` 上 `…0800`。相同数字种子不是相同随机流；ENLOG 未给 Rust 同格式抽样请求 tape，故不能配对这两次故障。 |
| PM | `system PM task … started/completed`，相邻 `PMID: PM_25H/PM_50H`；小时和原生机序位 | `preventive_created/completed`，`due_dimensions`、活动、尾号；分钟 | 原生 48 个 PM 作业，首个第 10884 分钟；Rust 58 个，首个第 1440 分钟，源于一架飞机的日历到期。原生候选未表达 7 日或 25 飞行小时复合条件及逐机初始寿命，不能认定同一 PM 触发。 |
| CM / 修复 | `System to repair`、`Start/Finished repair of item`，原生系统/部件实例和小时 | `maintenance_method_selected`、`repair_completed`、作业/组件 ID 和分钟 | 原生 19 次系统送修、33 次物项修复启动；Rust 10 次 `repair_completed`。触发故障、物项树修复路径和库存事务不同，计数单位也不同；尚无可接受的逐维修配对。 |
| 人员/设备 | `resource availability test` 的缩进 `RID/QTY/OK|failed`；`allocated/deallocated … maintenance task: Q available now: N`；`BASE` | `resources_reserved/released` 的节点、步骤、`personnel/equipment` 与占用量 | 原候选在第约 308 分钟对工序 2 每机占用通用人员/设备各 1，另占 `P_MECH/P_ARM/P_SPEC/P_AVION` 各 1；Rust 只占通用各 1，这是**首个确定性资源语义差异**。受控副本只移除 27 条起飞前专业需求后，原生通用资源与其余选定事件投影在 seed 1 全程一致；这只说明这些额外资源在该容量下没有改变选定事件。 |
| 资源等待、DTIM | 缩进可用性检查 `failed`、任务取消时刻；`OperationProfile.DTIM` 小时 | `resources_reserved` 与等待/取消 trace；Plan `cancel_minutes=20` | `P_ARM=1, DTIM=20` 副本有 4070 次失败检查（**重试检查，不是独立等待事件**），26 波开始、78 波取消；其中 77 波约在计划时刻后 20 分钟取消，1 波提前约 121.98 分钟取消。`DTIM=NULL` 默认 0 的受控副本有 3722 次失败检查、12 波开始、92 波均在计划时刻取消。两副本均未观察到实际晚起飞；20 分钟窗的事件级影响体现为取消时点和保留波次。见两份 `resource-and-dtim-audit.json`。 |
| 库存、欠交、转运 | `Item demand arrives`、`Backorder added/removed`（后续行有 `Nbr`）、`Replacement item arrives`、`Take/Put back … stock`；部件实例、站点、小时 | `shortage_events`、库存资源节点、运输路线与 trace；分钟、稳定产品 ID | 原生 seed 1 记 33 次物项需求、32 次新增欠交；Rust seed 1 指标为 0 次备件需求、0 次短缺。此差异首先受故障轨迹影响，不能单独判库存规则错。日志中未观察到可证明基地→基层 120 分钟物项转运的开始/到货配对；大量 `check for return transport` 指人员/设备返程检查，不能充当库存调运。 |
| 停止与输出 | ENLOG 至 `Time: 1032` 小时；报告 0–1032 小时，30 分钟区间；`mission success` 79 行 | `time=61464` 分钟、`natural_complete`；成功 82/104 | 观察终点相差 456 分钟。SIMLOX `MTMF/STMF` 为时间加权量，不能替代 Rust 波次成功率。当前输入和口径尚未通过全时段对齐。 |

## 随机与顺序约束

`Control.RSEED=1` 与 Rust `seed=1` 不能用数字相同代替算法、抽样点和调用顺序配对。原生故障发生于小时小数时刻，固定 Plan 使用 `legacy-minute-v1`；直接比较原生打印时刻与整分钟事件也会混入时间量化差异。ENLOG 保留文本行顺序，但不暴露 Rust `sample_requests` 同结构的随机请求身份/返回值，且一些数量和部件对象位于后续缩进行。`extract_enlog.py` 保留原始行号、文本及这些后续行，只把明确识别的行分类；未识别的诊断行不被静默认作已映射事件。

当前语义门槛**未通过**：任务/故障/PM/维修/资源/库存/终点不全等价。不得做“等价 1000 样本”速度比。
