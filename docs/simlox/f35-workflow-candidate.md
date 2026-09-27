# F35 保障、预防维修、修复维修工序候选模型

状态（2026-09-26）：已在 4700-3 的 SIMLOX 2017 中完成 JSON 导入、原生 `.sxi` 保存、原生表回导、一次 43 天运行和结果导出。**工序和汇总资源需求已进入可运行模型；与 `spare_mvp` 的执行语义仍未验收。** 本文只记录这次增量；基础模型来源见 [F35 候选模型](f35-candidate.md)，全部 30 道工序的源作业、时长、前驱、声明工种/设备和 SIMLOX 行号见 [机器可读映射](f35-workflow-mapping.json)。

## 来源和原生证据

| 对象 | 固定身份或 SHA-256 |
| --- | --- |
| 工作树 | 从 `e9b6391fffd918e0f6e742bd1ef0e1312921b769` 创建的独立分支 `codex/simlox-semantic-alignment`；与 #6 的性能工作分开。 |
| canonical 输入 | 上游 `spare_mvp` 提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`；`simulation-inputs.json` 文件 `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`；规范输入指纹 `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`。 |
| 已验收的执行计划 | `execution-plan.json` 文件 `548f77dfc61b9c545f5ac17eefcd5443f265a1530818696f9cafed7c3dd97298`；Plan 指纹 `f3a055330fe3c03bb9d47c745e12fdaeae11ac29ff355c1751534163fc7da256`；`work_policy=stable-topological-serial`。 |
| SIMLOX | `Simlox.exe` product version `2017.0.0.0`，SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；原生数据库版本 `20160627`。安装目录 `UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt` SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`。 |
| 新候选 JSON | `f35-workflow-v4-candidate.json` SHA-256 `e32bb75b94b44573d208fe415243c223de88802f1e3df99c8bd2ab47ff772e6a`。生成脚本：[build_f35_workflow_candidate.py](../../scripts/simlox/build_f35_workflow_candidate.py)。 |
| 原生输入/输出 | `.sxi` `cf7e7730b55015f5a20c8edb691810865f4dbbf040a113192121d53cdd43df81`；原生回导 JSON `a73c6295d5e93bf93d84d610ce89edfcde9d7d15c60c6c482a6756650055611f`；`.sxo` `6b95885308f294b0f2a5364be3bf072aedbe23c78f74f22cd5b4bb76f09ad873`；原始结果 JSON `db8600eb0c99f5f615a46908b80e4395fcb7356ba272495b1090d2b2335f1037`。 |

4700-3 原始文件在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-workflow-v4\`。本工作树 Git 忽略的镜像在 `data/local/simlox-f35-steps/v4/`，含 `.sxi`、`.sxo`、原生回导、原始结果、导入/运行/导出日志和 `verification.json`；候选 JSON 与完整映射在 `data/local/simlox-f35-steps/`。原生报告尾随逗号只在校验时于内存中移除，未改原始字节。哈希和逐表回导由 [verify_f35_workflow_candidate.py](../../scripts/simlox/verify_f35_workflow_candidate.py) 核对。

## 逐项对齐

SIMLOX 安装手册 `UserDoc/SIMLOX.pdf` 的 `TaskBreakDown`、`SubTaskResource` 和维修段落规定：子任务按顺序执行；子任务有需求时覆盖整任务的 `TaskResource`；换件维修使用 `<REMOVE>` 和 `<REPLACE>`。本候选按这些原生关系建模。

| 范围 | canonical / 已验收 Plan | SIMLOX v4 行与效果 | 对齐程度 |
| --- | --- | --- | --- |
| 使用保障 | `f35-service-0103` 的 14 个作业按 Plan 的稳定拓扑顺序串行，总名义时长 142 分钟。 | `MissionPreparation.TID=MISSION_PREP`、`DURN=142/60` 小时；14 条 `SubTaskType`、14 条 `TaskBreakDown`，序号和时长逐项对应。 | 工序身份、顺序、名义时长已回导核对；仅表示起飞前准备，未覆盖 canonical 的完整 `daily-v1` 预约、取消、返场及再次出动。 |
| 预防维修 | `preventive-f35-6` 和 `preventive-f35-50h-24h` 各有 1 个已验收 Plan 作业，均为 1440 分钟。 | 两条 `MaterielPM` / 两条 `PMLocation` 仍使用 25、50 飞行小时触发；各增加一条 `<INSPECT>` `TaskBreakDown`，24 小时，关联原 PM `TID`。 | 工序和时长已核对；7 个日历天或 25 飞行小时的 OR 触发、各机初始寿命、阈值复位与重叠 PM 规则未对齐。 |
| 修复维修 | 6 个专属纠正活动加 1 个通用回退；每个对应 1 个 Plan 作业，时长分别为 180 或 30 分钟。 | 7 个 SIMLOX 维修任务各分为 `<REMOVE>`、`<REPLACE>` 两条顺序工序，合计 14 条；`SystemRepair` 1 条在 BASE 提供回退，423 条 `ItemReplacement` 按部件指向相应任务。运行中出现故障和系统修复状态。 | 总名义时长已对应；源作业没有拆卸与装入各自时长，故 50/50 分拆只是明确的近似。拆下件的 `ItemRepair.DIRPT=0` 是即时整修占位，库存事务和修复方法不等价。 |
| 资源需求 | Plan 每道工序 `personnel=1`、`equipment=1`；源作业另有工种/设备名称。节点只给总容量 40 人、60 台设备。 | 两种 `Resource.TYPE=SPECIAL` 汇总资源保持容量 40/60；30 道工序各有 1 人和 1 设备的 `SubTaskResource`，共 60 条，`RPROB=1`。 | 汇总容量与逐工序需求已在 SIMLOX 生效。源声明的 4 个工种、6 种设备名称写入工序 `NOTE` 和映射文件；没有各类容量，不能声称类别化竞争等价。 |
| 故障率单位 | canonical 故障率按每运行小时。 | `Item.FRT`、`System.FRT` 从原候选数值各乘 `1,000,000`，`OPID=OPHOURS`；SIMLOX 手册 `FRT` 单位为每百万 OPIDs 的故障次数。 | 单位换算已回导核对。故障暴露、父子故障逻辑、随机流及因果归属仍未对齐。旧候选直接写每小时数值，故障负载过低。 |
| 结果 | canonical 要求逐事件轨迹、请求 tape、指标和终态。 | 原生报告 `NREP=1`、0–1032 小时；2064 个 `SystemResults` 行、2064 个 `ResourceResults` 行；17 个区间行 `NFAIL>0`，656 个区间行 `NSYPM>0`，95 个区间行 `NSYRP>0`。 | 证明三类工序及故障/维修路径被模型执行；这些是**非零区间行数**，不是事件次数。SIMLOX 聚合指标分母和 canonical 输出仍未配对。 |

使用保障 14 道工序的分钟数依序为 `8, 6, 4, 4, 14, 5, 5, 23, 20, 5, 4, 13, 23, 8`，合计 142。完整作业代码、来源声明的人员与设备及 Plan 前驱在 [映射 JSON](f35-workflow-mapping.json) 中，不从 SIMLOX 行号反推业务身份。源作业有时同时声明多个专业或设备，而已验收 Plan 的顶层 `required_personnel=1`、`required_devices=1` 折算为各一份汇总资源；本候选遵循 Plan 口径，未臆造分类容量。

Plan 共 13 个活动；本候选的 10 个 SIMLOX `Tasks` 对应上述 1 个使用保障、2 个 PM 和 7 个 CM。其余 `f35-service-0103-relaunch`、`f35-service-0103-postflight` 和 `logistics-34` 在该 Plan 中没有工序，因此未凭空增设 SIMLOX 工序；它们相关的调度和物流行为仍在语义缺口内。

## 原生验证与资源争用探针

`verification.json` 的状态为 `native-roundtrip-and-run-verified`。校验覆盖 `System`、423 个 `Item`、10 个 `Tasks`、14 个 `SubTaskType`、30 个 `TaskBreakDown`、60 个 `SubTaskResource`、2 个 `Resource`/`ResourceAllocation`、1 个 `MissionPreparation`、423 个 `ItemRepair`、1 个 `SystemRepair`、423 个 `ItemReplacement`、2 个 `MaterielPM` 和 2 个 `PMLocation` 的关键字段。v4 运行日志明确配对该 `.sxi` 与 `.sxo`，输入转换为 **0 错误、0 警告、0 提示**，未见运行警告。一次诊断运行的 `Simulation time=0.18 s` 不构成性能基准。

原容量 40/60 下 `ResourceResults.NRW` 的非零区间行为 0。另以完全相同候选 JSON 只改两处 `ResourceAllocation.RQTY` 为 1/1，作为**独立容量探针**运行；该探针 JSON SHA-256 `8e4ea141cf4b1d2618e0d996a0291802582a0ec80c68a7a9af3dd60adbd6faad`，原生转换仍为 0 错误/警告/提示，`NRW` 非零区间行为 286。原始探针证据在 4700-3 的 `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-workflow-capacity1\`，本机镜像 `data/local/simlox-f35-steps/capacity1/`。这验证 `SubTaskResource` 在 SIMLOX 中产生资源等待；探针改变了负载执行，不用于 canonical 结果或效率比较。

早期尝试保留在忽略目录：`STANDARD` 类别资源触发 SIMLOX #495 警告并被忽略；未换算 `FRT` 的版本无故障；缺少终点站 `SystemRepair` 的版本触发 #242 警告。v4 修复这些原生建模问题。仍需任务派遣、PM 复合触发、换件库存、随机流、资源排队顺序和输出分母的独立语义验收，之后才能对这个新模型测量并比较效率。

后续只增加上级库存并建立站点关系的独立变体见[备件调运探针](f35-depot-stock-probe.md)。该变体已通过原生回导和运行，但 SIMLOX 汇总结果尚未证明备件实际调运。
