# SIMLOX 与 canonical 输入的配对检查

后续的 F35 原生候选模型及其已验证范围见 [F35 原始候选](f35-candidate.md)、[补全工序、资源与故障率单位的候选](f35-workflow-candidate.md)及[上级库存和调运探针](f35-depot-stock-probe.md)。AMD128 主仓库较新的 8 架 J35 项目另见 [J35 页面数据逐项对照及原生候选](j35-page-candidate.md)与[首批输出口径验收](j35-output-semantics.md)；它与旧 9 架 F35 模型独立。这些候选均有明确的语义缺口，不能用于跨引擎效率对比。

状态（2026-09-26）：**四个 SIMLOX 示例各自的模型与既有结果已在来源主机上配对；尚无一个示例与本仓库的 canonical `simulation_inputs` 配对。** 本记录是从 `e9b6391fffd918e0f6e742bd1ef0e1312921b769` 创建的独立工作树中的证据提交，与 #6 的测量和修改分开。本节四例配对只核对既有结果；后续 F35 候选的建模与新运行另见上方链接。

4700-3 的 Codex 在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-alignment-evidence` 采集了 12 份原始导出（四个原 Demo 模型、四个既有 `run1` 模型、四个既有结果）。本仓库仅保存[来源 manifest](source-manifest.json)、[来源与导出方法](source-provenance.md)、[SIMLOX 表关系与实际行](source-relations.md)和[原机状态](source-status.md)；原始导出保留在该 Windows 目录，并复制到本工作树被 Git 忽略的 `data/local/simlox-alignment/`。来源笔记中的 `raw/` 均指 Windows 采集目录下的 `raw/`，不属于 Git 跟踪内容。 Windows Codex CLI 采集会话为 `01a0db9d-ac52-7470-a616-b9a3dcccb620`。`source-manifest.json` 的 `baseline_verified=false` 只表示原机没有本仓库 checkout；本工作树已用 `git rev-parse e9b6391^{commit}` 核对基点。

## 来源、版本、指纹

| 证据 | 身份与指纹 |
| --- | --- |
| SIMLOX 程序 | `Simlox.exe` 的 Windows product version 为 `2017.0.0.0`，文件版本字符串未填；SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`。四份运行模型导出的 `model.database_version` 均为 `20160627`。 |
| SIMLOX 表字典 | `UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt`；SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`。表关系 PDF 与用户手册的路径、大小和 SHA-256 见 manifest。 |
| 本仓库固定 canonical | 上游 `spare_mvp` 提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`，`project_version=import-v1`、`schema_version=aircraft-support-v1-input-v1`、`execution_plan_version=aircraft-support-plan/v1alpha2`；唯一入口为 `ProjectJsonExporter` → `SimulationAdapter` → `integrations/spare_mvp`；fixture 为 `tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json`，文件字节 SHA-256 `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`，manifest 中的规范输入 SHA-256 `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`，Plan fingerprint `f3a055330fe3c03bb9d47c745e12fdaeae11ac29ff355c1751534163fc7da256`。这些是三种不同的指纹，不能互换。 |

每个 SIMLOX `run1.sxi` 与相应 `.1000.sxi` 的 SHA-256 一致；原日志写明 `run1.sxi` 与 `run1.sxo` 的路径，结果 `ResultSummary.NREP=1000` 与输入 `Control.NREPS=1000` 一致。结果文件没有单独核对到内嵌的输入哈希或运行 ID，因此配对依赖原日志和路径。原 Demo 与 `run1` 导出表结构也不同，不能仅凭既有说明认定两者只改了重复次数。

| 案例 | `run1.sxi` SHA-256 | 模型 JSON 导出 SHA-256 | 结果 JSON 导出 SHA-256 |
| --- | --- | --- | --- |
| `aircraftorg` | `2fb830592d0764387f3ca6b54b5bebfde7e320b364c24dd1afc5925271c24ffa` | `ea015e253509f877d940f6a17735c177f9b53a11f47b2c85d7ea9b5248673673` | `312100b4660c7aad270e47c04fed4e745d846dfccbb63ae02837def8b42cdf66` |
| `Torpedo Case` | `b4fe06d3c2130914727425008e5e6db212f6f7641a9dee8c733263f4b837cff3` | `f58d38349c62c39e2516a6c0995db39c6b6a51398b907bbf26d827b9a0743820` | `a3b4ee6a1f638b77987a914bbb30124587ab435754bca3c3a4525861d1dae756` |
| `wbend` | `26f9872f4ff3c580b1fbaeef0a7618e4022617cddafcfc47a35dfd2b5fb68a40` | `eeaade71e7d7c5f7a785f7a129f6cba53679d6e8159180bc89d5a7d47735d8d4` | `02d9c9c85a0bb36000de28e6422e2a0ba1667dc0b153b7977d1909a063e9f550` |
| `wbT2fix` | `6171189b631ad1a75cc5161209fb1bd8300a1670fcb0c7f36123722f95142e74` | `b6c1b8bd97a05021e09a07027620244782c18421c92782ce9df48d223a974adf` | `5011af87dcc5e014ffed130dc114972785f5463eb5b4572cbba8dea2343e0e56` |

原始 `-jsonreport` 结果有数组末尾多余逗号，不符合严格 JSON。manifest 保留原始字节哈希；摘要解析仅在内存中删除闭合括号前的多余逗号，不改写原始文件。所有原始导出命令、退出码、源路径和大小都记录在 manifest。

## 逐项语义对齐表

下表将官方字典中的关系、实际 `run1` 模型/结果行和本仓库固定 F35 canonical fixture 分开。**“结构候选”仅表示概念上可研究映射，不是模型或执行语义已对齐。** `aircraftorg` 是最接近飞机保障的示例：它是 Fokker F28，部署到 ARN 的 4 架和 CPN 的 6 架；F35 fixture 是另一组 9 架飞机。`Torpedo Case` 和 `wbT2fix` 用于补充观察任务与资源字段，不拼接成一个虚构的 SIMLOX 案例。

| 核对项 | SIMLOX 官方关系与实例证据 | canonical F35 对应位置 | 本次结论与配对缺口 |
| --- | --- | --- | --- |
| 模型与运行边界 | `aircraftorg` 的 `System.SID=FOKKER_F28`；`Control.SIMPE=8760` 小时、`NREPS=1000`、`RSEED=123456789`。 | `project_identity` 为 F35 案例；`aircraft.assets` 9 架；`time.duration_minutes=61920`（1032 小时）；`monte_carlo.sample_count=1`、`seed=0`。 | **实值不配对。** 必须固定同一模型、期限、样本身份和随机合同。 |
| 任务类型与需求 | `MissionType.MTID/NOS/MNOS/DURN`；`aircraftorg` 有 `MT1`、`MT2`，`MT1.NOS=2`、`MNOS=2`、`DURN=1000` 小时。 | `mission_profile.basic_missions` 的 `equipmentQuantity=2`、`minRequiredSorties=2`、`taskDurationMinutes`。 | 结构候选；任务身份、持续时间和成功条件尚未统一。不能因数值 2 相同就认定同一任务。 |
| 任务生成、排序、派遣 | `Operations.USTID→OperationProfile.PRID`，`SPRID→MissionType.MTID`；F28 `REGENERATIVE` profile 以 8760 小时为周期。 | `mission_profile.composite_tasks`、`mission_calendar` 的 26 个任务日、四组日波次；Plan `daily-v1` 时间阶段与预约规则。 | **未对齐。** 生成方式、优先级、替补、同刻顺序和任务取消需要同一案例的逐事件证据。 |
| 故障对象与时钟 | `Item.IID/FRT/OPID`、`FailureMode.FMID/MID/FRQ/OPID`；F28 `ENGINE.FRT=110`，但四份运行模型均无 `FailureMode` 表。 | `equipment_tree.components` 的 424 项及 `failure_rate`、`failure_distribution`，计划中的飞行暴露量与 RNG 请求。 | 结构候选；`FRT` 的有效单位、默认 `OPID`、暴露时钟、采样/重置时机未核对，不能直接换算为 canonical 故障率。 |
| 纠正维修与换件 | `SystemRepair`、`ItemRepair` 用 `SID/IID`、`STID`、`DIRPT/SURPT` 和可选 `Tasks.TID` 定义；F28 在 CPN 的系统 `SURPT=2.5` 小时。 | `support_activities.activities` 的 `corrective` 作业、步骤、地点、维修方式、工作时长与库存事务。 | 结构候选；维修选择、工序顺序、完工时状态及换件账本未配对。 |
| 预防维修 | `MaterielPM/PMLocation` 为正式关系；`aircraftorg.Control.ENPM=N` 且模型无 PM 行。`Torpedo Case` 有 `PMINT=168`、`OPID=CALHOURS`、`ENPM=Y`。 | `support_activities.activities` 的 `preventive` 作业和资产预防阈值/周期。 | **F28 实例不覆盖该行为。** Torpedo 案例的 PM 不能填补 F28 的缺口。 |
| 人员、设备与资源竞争 | `Tasks/TaskResource/ResourceAllocation` 为关系。F28 模型没有 `Tasks`、`TaskResource`、`Resource` 或 `ResourceAllocation` 行；`wbT2fix` 有任务需 1 名 `TESTER`，站点配置 2 名。 | `support_network.nodes` 的人员/设备容量，`support_activities.activities` 的 `required_personnel/required_devices`，Plan 等待队列与资源预约。 | F28 **没有可比的容量竞争输入**；另一个示例仅证明有容量约束，报告聚合值不能重建等待顺序。需同一模型中至少两个争用作业及 trace。 |
| 库存、站点、运输 | `StockAllocation.POINT/IID/STID/STSIZ`、`StationStructure.STID/MSTID/TFRMS/TTOMS`；F28 `APU` 在 CENTRAL 库存 7。 | `support_network.nodes.inventory`、`organization_graph` 与运输策略、步骤备件需求。 | 结构候选；产品身份、数量、预约、补给次序与运输时长未配对。 |
| 输出采样与分母 | `Control.RCINT=730` 小时；结果 `ResultSummary` 覆盖 0–8760 小时，`MTMF=0.9438642859`、`STMF=0.9444889426`；`SystemResults` 与 `StockTotalResults` 各 12 个区间行。手册将 `MTMF` 定义为已完成的规定任务时间除以规定任务时间。 | `time.sample_every_minutes=30`，结果有 `mission_success_rate`、`operational_availability`、库存/停机等指标及独立终态。 | **口径未对齐。** 时间区间、权重、分母、缺失值和终止状态都需逐字段定义；数值不能直接比较。 |
| 事件与 RNG 证据 | 四份 `-jsonreport` 输出为聚合表；没有逐事件任务、故障、维修、资源等待或抽样请求 tape。 | 固定 oracle 有 `trace`、`sample_requests`、`metrics`、`terminal_state`，可定位首处分歧。 | **验收证据缺口。** 只有聚合均值不能验证时间顺序、随机调用或资源事务。 |

## 进入语义验收与效率比较的条件

1. 选一个**同一业务案例**在 SIMLOX 原生模型和 `spare_mvp` 上游 Project 中完整表达，经既有 `ProjectJsonExporter`/`SimulationAdapter` 生成 canonical 输入；保留双方源版本、输入指纹、单位换算、默认值与稳定实体映射。不要在编译器内另建 Project JSON 解释器。
2. 对任务、故障、维修、预防维修、资源/库存竞争和输出指标分别固定可手算或可重放的案例。至少核对同一 horizon、种子或随机流合同、事件/预约账本与未完成状态；缺少逐事件导出时明确降低验收范围，不用均值接近代替语义差分。
3. 同一模型与输出配置完成语义验收后，再独立记录编译、初始化、执行、端到端耗时，且不把既有四例 SIMLOX 计时与 F35 结果相除。#6 的性能证据保留在它自己的工作树和报告中。
