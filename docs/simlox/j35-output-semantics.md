# J35 输出口径的首批验收

状态（2026-09-26）：**3 项输入/分母口径和报告内部算术已验收；任务事件、随机流、可用度、库存与资源等待尚无跨引擎等价结论。** 本次沿用 [8 架 J35 原生候选](j35-page-candidate.md)及固定 Plan，没有重建模型或测量运行效率。逐数审计及原始文件指纹见 [机器可读审计结果](j35-output-audit.json)，计算程序见 [audit_j35_output_semantics.py](../../scripts/simlox/audit_j35_output_semantics.py)。

原始 SIMLOX `-jsonreport` 保留在 4700-3 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-page\j35-page-result-raw.json`，本机镜像为忽略目录 `data/local/simlox-amd128-page/`。Python reference 在固定 Plan 上分别执行种子 0、1，原始结果保留于同一忽略目录。审计程序核对这三份运行结果的 SHA-256、Plan 与模型指纹；对 SIMLOX 报告只在内存中清理其数组尾部多余逗号。

| 口径 | 实际检查与结果 | 验收判定 |
| --- | --- | --- |
| 输入期限与采样粒度 | 两边输入都是 43 天：Plan `duration_minutes=61920`，SIMLOX `Control.SIMPE=1032h`。SIMLOX `ResultSummary` 为 1 次重复、0–1032 小时，`SystemResults`、`StockTotalResults`、`ResourceResults` 各连续 2064 个 **30 分钟区间**。canonical 的计划采样间隔也为 30 分钟。 | **通过：输入期限、报告时段和区间粒度。** 这是配置及报告覆盖检查，不代表每个时点的状态等价。 |
| 计划任务分母 | 固定 Plan 和 SIMLOX `OperationProfile` 都有 104 波；SIMLOX 的 `MSTF=0.8846153617≈92/104`，`MSUF=0.7788461447≈81/104`。手册将两者分别定义为**已开始固定任务数/计划固定任务数**、**成功固定任务数/计划固定任务数**。 | **通过：104 波分母及 SIMLOX 内部整数计数可还原。** 当前 `-jsonreport` 没有逐波 `Fixed Mission` 行，92 和 81 仅由单次汇总分数还原。 |
| canonical 成功率算术 | reference 种子 0：开始 69 波、成功 63 波，`mission_success_rate=63/104=0.6057692308`；种子 1：开始 89 波、成功 82 波，`mission_success_rate=82/104=0.7884615385`。计数由终态逐波记录和 `metrics` 双向核对。 | **通过：canonical 自身的分子、分母和终态计数。** 两边成功分数在数学形式上均为“成功波次/104”；SIMLOX 为 81/104，与 canonical 种子 1 的 82/104 只差一波，但这**不是**事件或随机样本配对。 |
| 成功时点 | 两边输入 `MSUCPT/success_point=0.75`，任务时长均采用 324 分钟；canonical 在起飞后 `ceil(324×0.75)=243` 分钟检查剩余参与机数是否至少 2。SIMLOX 手册将 `MSUCPT` 定义为达到任务时长该比例即计成功，且只影响结果计算。 | **部分对齐：参数与名义时点。** SIMLOX 中途中止、系统数减少、替补和任务完成的计数规则无逐任务证据，不能据此验收成功事件语义。 |
| 实际停止时点 | reference 种子 0 在 61920 分钟以 `duration` 停止；种子 1 在 **61464 分钟**以 `natural_complete` 停止，比 SIMLOX 报告上界早 456 分钟。Plan 对上游默认停止策略启用了自然完成。 | **种子 1 不满足相同观察终点。** 两边都已覆盖 104 个计划开始时点，因此可核对波次分母；时间平均、等待时间及终态不能按同一 43 天窗口直接比较。 |
| `MTMF`、`STMF` | SIMLOX 两者本次均为 `0.8405485153`。手册：`MTMF` 是完成的**任务运行时间/规定任务时间**；`STMF` 是完成的**系统在任务中运行时间/规定系统时间**，都排除任务前准备与任务后周转。导出的 `SystemResults.STREQ` 2064 行总和为 0，无法由当前区间表重建 `STMF` 分母。 | **不可映射为 canonical `mission_success_rate`。** 两个时间加权比率与 81/104 波次比率不同；当前报告不足以逐时重算任务/系统时间分母。 |
| 可用度与就绪数 | SIMLOX `SystemResults.NSYRY` 的 1032 小时时间平均为 **5.364692 架**，除以 8 为 `0.67058655`。手册称 `NSYRY` 为可接新任务、未被分配且未在维修的系统数；在途任务飞机不算就绪。当前 Python reference `metrics` **没有导出** `operational_availability`，也没有同定义的 30 分钟就绪序列。 | **未验收。** `NSYRY/8` 是本 SIMLOX 模型的平均“可再派遣比例”，不能命名为两边共同的使用可用度。 |
| 库存短缺 | SIMLOX `StockTotalResults.NBO` 为各区间平均未满足需求数：1032 小时时间平均 `0.04723837`，积分 `48.75` 件·小时，108 个区间非零；手册明确转运欠交不计入 NBO。canonical `shortage_events` 是去重后的短缺事件计数：种子 0 为 3、种子 1 为 0。 | **未验收。** 平均欠交量、欠交时长与短缺事件个数不是同一量纲；当前 SIMLOX 总库存表缺少逐件请求、预约和转运账本。 |
| 资源等待 | SIMLOX `ResourceResults.NRW` 是**未满足维修资源需求的平均队列**，本次 2064 区间均为 0；reference 种子 0、1 的 `personnel_delay`/`equipment_shortage` 轨迹行均为 0。SIMLOX 模型同时占用通用和页面专用资源。 | **未验收跨引擎等价。** 零值只说明这两个独立样本未观察到对应等待；平均队列与按分钟发出的延迟轨迹计数不同，且资源约束尚未对齐。 |

SIMLOX 手册依据：4700-3 `C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf`，印刷页 265（`MSUCPT`）、531–532（结果间隔）、552–553（四项汇总分数）、631（`NSYRY`）、684（`NBO`）、750、755（`NRW`）。手册与表字典的原机指纹见[来源记录](source-provenance.md)。

下一步若要验收 **81 与 82 波的首处分歧**，需要 SIMLOX 每波开始/成功记录以及故障、准备和资源预约的事件证据；目前只有聚合汇总，不能通过分数接近推断两个执行过程相同。
