# AMD128 主仓库 J35 页面项目与 SIMLOX 原生候选

状态（2026-09-26）：**结构数据已补全、原生导入与单次运行已验证；跨引擎执行语义和指标口径尚未验收。** 用户选择 AMD128 主仓库较新的 J35 页面项目。本模型是独立的 **8 架 J35** 候选，未覆盖此前 9 架 F35 候选，也未将它与本仓库旧 F35 固定 oracle 混为同一输入。

## 来源与可复核边界

| 层次 | 版本、身份和 SHA-256 |
| --- | --- |
| 页面项目底层记录 | AMD128 `/home/g/Models/spare_mvp`，`main=origin/main=0e709bdcc2d692d9cfed49b9037c76ef71aefe33`，工作树干净。只读访问原机 SQLite，未复制数据库。项目 `project-j35-8aircraft-43day-availability-20260909`，页面更新记录 `2026-09-23 03:00:20.376-f9ffc539`，原 `payload_json` SHA-256 `bce310581ae8b2fdf1fcd28f76065a673e63746f9b39be5152393d5c67287a7e`。 |
| 上游正式转换 | 在 AMD128 用该仓库 `ProjectJsonExporter` 导出干净 Project JSON，SHA-256 `aa285af2abcea77d8244f16599284259d4a3ac57288ee0b5afc8a626566744d7`，`project_version=import-v1`、`schema_version=project-v0`；再用 `SimulationAdapter.compile_scenario_with_gate(..., model_family="aircraft_support_v1")` 得到 `simulation_inputs`，门禁 `compiled`、0 issues，文件 SHA-256 `30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559`，输入规范指纹 `d9aa54e27d152bab775e3653a1025e42457ea9900e454849ec0d65c6c9cc65c5`。适配器 `mapping_provenance` 文件 SHA-256 `47cef440d85269cbcb6669117f8ab28a56a9e3657e9afee1945c0f1ac42a1e2a`。 |
| 独立 Plan | 本仓库编译上述 canonical 输入，`plan_version=aircraft-support-plan/v1alpha2`、`semantic_profile=legacy-minute-v1`、`rng_profile=legacy-sequential-v1`、`work_policy=stable-topological-serial`；Plan 文件 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，Plan 指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`。这是静态编译通过，**不是 J35 运行差分验收**。 |
| SIMLOX | 4700-3 上 `Simlox.exe` product version `2017.0.0.0`，程序 SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；数据库版本 `20160627`。只借用原 F35 v4 原生回导 JSON 的 31 张表模式，原始回导 SHA-256 `a73c6295d5e93bf93d84d610ce89edfcde9d7d15c60c6c482a6756650055611f`，仓库模板仅将 CRLF 换为 LF，SHA-256 `aec7d1049aced4c2842081c106ad19b7cd3248c2dd168e5bf278bd3920f610f9`；J35 业务值来自上面固定导出。 |

完整组件、库存、工序、资源映射见 [机器可读逐项表](j35-page-mapping.json)。可核对的 Project、canonical 和 Plan 快照分别存于 [J35 来源目录](../../tests/fixtures/spare_mvp/j35-amd128-0e709bd/README.md)，SIMLOX 表模式来自 [原 F35 原生回导模板](../../tests/fixtures/simlox/f35-workflow-v4-native-template.json)。生成器 [build_j35_page_candidate.py](../../scripts/simlox/build_j35_page_candidate.py) 固定四个输入文件字节指纹，遇到项目身份、结构计数、活动或资源映射漂移时显式报错。原始页面记录、转换来源日志及生成的 SIMLOX 文件留在本工作树被 Git 忽略的 `data/local/simlox-amd128-page/`；原生 `.sxi` 与原始运行文件还保存在 4700-3 的 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-page\`。没有把原机数据库放进仓库。

## 页面建模数据到 SIMLOX 的逐项对照

| 建模项 | AMD128 J35 页面 / canonical / Plan | SIMLOX J35 原生候选 | 状态与界限 |
| --- | --- | --- | --- |
| 项目、期限与机队 | 43 天 = 61920 分钟；8 架 J35，尾号 J35-01…08，均初始可用。各机已有不同的日历/飞行小时/起落初始寿命，例如 J35-02 页面原值 20 天，canonical 归一值 6 天。 | `Control.SIMPE=RCEND=1032` 小时，`SystemDeployment.QTYPS=8`。 | 机队总量和期限配对；聚合部署未保存尾号与逐机初始寿命。页面原值与 canonical 归一值需按适配器来源字段区分。 |
| 基本任务与日历 | `BM-J35-43D`，每任务需 2 架、最低 2 架，成功点 0.75；26 个任务日，每日 08:00/09:00/10:00/11:00 共 104 波。提前 180 分钟，取消窗 20 分钟。页面基本时长 234 分钟；Plan 阶段修正后 324 分钟。 | `MissionType.NOS=MNOS=2`、`MSUCPT=.75`、`NOPER=3h`、`DURN=5.4h`、`TFOUT=.3`、`TFRET=.3`；104 行 `OperationProfile`。 | 身份、数量、开始时间、Plan 时长已落表并回导。SIMLOX 的派遣、替补、取消、阶段和同刻排序未与 `daily-v1` 执行语义对齐。 |
| 使用保障 / 起飞前准备 | 页面 `J35使用保障` 总时长字段 148 分钟，canonical 活动聚合 120 分钟；Plan 选中的 14 个串行工序合计 **142 分钟**。 | `MissionPreparation.DURN=142/60h`，`Tasks/TaskBreakDown` 保存 14 道工序；SIMLOX 在每次任务前请求准备。 | 工序顺序和时长按 Plan 逐项补齐；三种来源的时长口径保留差异。再次出动和飞后检查虽有活动身份，却没有可执行步骤，不能说已建成独立作业。 |
| 故障对象与速率 | 424 个组件（含根），423 个子件均声明指数故障分布；每小时故障率和父子数量来自 canonical。 | 1 个 `System`、423 个 `Item`、423 行结构；`OPID=OPHOURS`，`FRT` 为子树速率换算成每百万运行小时。 | 身份、结构、单位和输入数值已落表；父子因果归属、飞行暴露、采样时机与 RNG 流尚未证明等价。不能由转换成功推断故障语义一致。 |
| 预防维修 | `preventive-j35-6`：**7 日历天或 25 飞行小时**；另有 50 飞行小时周期。两项均各 1440 分钟，Plan 还有逐机初始寿命。 | 两个 PM `Tasks` 和工序，各 1440 分钟；原生 `MaterielPM/PMLocation` 模式保留。 | 工序和小时阈值候选已落表；7 天 OR 25 小时复合触发及逐机初始寿命缺失。 |
| 修复维修 | 6 个件类专用修复活动加 1 个通用活动；Plan 各 1 道工序，时长为 30 或 180 分钟。 | 423 行 `ItemReplacement` 按 Plan 所选活动关联；SIMLOX 的 `REMOVE/REPLACE` 分两段各 50%，`ItemRepair` 的即时整修为占位。 | 选择关系、总时长可查；拆装比例、坏件整修、库存事务不是 canonical 的实测语义。 |
| 专业人员与设备 | 页面基层 4 个专业各 10 人：航电、军械、机械、特设；6 类设备各 10 台：加油车、挂弹车、空调车、电源车、牵引车、充氮车。canonical/Plan 还将每个选中工序归为通用人员 1、设备 1，基层总量 40/60。 | `Resource/ResourceAllocation` 保存四专业和六设备的 `SPECIAL` 类型各 10，加上通用 `PERSONNEL=40`、`DEVICE=60`；`SubTaskResource` 对工序同时施加 Plan 通用 1+1 与页面已定义的专用需求，共 89 行。 | 专业、数量、设备类型与数量已落表并被 SIMLOX 接受。**叠加约束会重复占用来源两种视图的资源**，所以资源竞争结果不是 canonical 的等价实现。 |
| **充氧工序例外** | 页面 `J35-USE-003` 声明机械 1、充氧车 1、4 分钟；但 10 个实际 `supportResources` 中没有充氧车的实例或容量。 | 保留“充氧”工序、4 分钟、机械专业 1，另保留 Plan 通用人员 1、设备 1；**不生成充氧车 `Resource` 或专用 `SubTaskResource` 需求**。 | 按用户要求排除未闭合的充氧车专用约束，映射的 `omitted_page_requirements` 精确记录该一项。通用设备需求仍在，不能称该工序无设备约束。 |
| 基地、基层库存与调运 | 页面有两个组织节点；基地 403 个品类全为 0，基层 403 个品类中 167 个为正、总数 501。基地→基层运输 2 小时、每批容量 1。 | `StockAllocation` 两站共 806 行，含零库存；`StationStructure` 基地→基层 2 小时。 | 产品/节点/数量已落表。SIMLOX 反向运输时间 2 小时为建模假设；来源每批容量 1 未表示，补库触发/预约未验收。没有把旧 F35 探针中人为增加的上级库存带入 J35。 |
| 其余活动与目录工序 | 页面共 13 个保障活动和 66 个目录工序；Plan 实际引用 23 个目录工序，43 个目录项未引用。再次出动、飞后检查、后勤活动均为零步骤。 | 14 准备 + 2 PM + 7 修复活动在 SIMLOX 展开成 30 条原生工序；零步骤活动和未引用目录项只记在映射，不虚构执行。 | 覆盖范围可审计；页面有活动名称并不等于有可执行过程。 |
| 随机与输出 | canonical 种子 0、`legacy-sequential-v1`，有逐事件、抽样请求、终态与 30 分钟采样口径。 | SIMLOX 拒绝种子 0，候选用种子 1；单次原生报告仅含 0–1032 小时汇总/半小时区间，`ResultSummary` 及系统、库存、资源表。 | 随机流、时间分母、任务完成/成功定义和等待队列缺少同口径证据；报告值仅说明本模型运行，**不能与 canonical 数值或效率直接比较**。 |

## 起飞前 14 道工序与资源要求

下表资源为页面声明，所有 14 道工序另有 Plan 通用人员 1、设备 1 的 SIMLOX 需求。`J35-USE-003` 的“充氧车×1”仅列作**源页面被排除的声明**，SIMLOX 不会等待该专用设备。

| 顺序 | 页面工序代码 | 分钟 | 页面人员专业 | 页面设备 |
| ---: | --- | ---: | --- | --- |
| 1 | `J35-USE-015` | 8 | — | — |
| 2 | `J35-USE-014` | 6 | 机械×1、军械×1、特设×1、航电×1 | — |
| 3 | `J35-USE-002` | 4 | 机械×1 | 充氮车×1 |
| 4 | `J35-USE-003` | 4 | 机械×1 | ~~充氧车×1~~（已排除） |
| 5 | `J35-USE-005` | 14 | 特设×1、航电×1 | 电源车×1、空调车×1 |
| 6 | `J35-USE-016` | 5 | 军械×1 | 挂弹车×1 |
| 7 | `J35-USE-009` | 5 | 军械×1 | 挂弹车×1 |
| 8 | `J35-USE-010` | 23 | 军械×1 | — |
| 9 | `J35-USE-011` | 20 | 特设×1、航电×1 | — |
| 10 | `J35-USE-013` | 5 | 军械×1 | — |
| 11 | `J35-USE-006` | 4 | 军械×1 | — |
| 12 | `J35-USE-007` | 13 | 军械×1 | 挂弹车×1 |
| 13 | `J35-USE-012` | 23 | 机械×1 | — |
| 14 | `J35-USE-004` | 8 | 军械×1、航电×1 | 电源车×1、空调车×1 |

## 原生验证与结果边界

4700-3 在无人占用 SIMLOX 图形进程时执行 `-jimport`、`-jexport`、`-calc`、`-jsonreport`，四步进程退出码均为 0。运行日志记录输入转换 **0 错误、0 警告、0 提示**；原生 `.sxi` 为 616675 字节，SHA-256 `a057b235615cc8db05a148c7bc2ed14509997c4c0d796aafa292c37d385f11e8`。候选 JSON SHA-256 `88033e3c83ed039c4ffff32da1f5c3b2ef91cd3a25318adac3020f30caece5c5`；原生回导 JSON SHA-256 `b2ff4b6acf8a9b3a14802abe460484956561da7f85a7bd91c915cb0f1d427901`。31 张表的 `instances` 行逐项相同。原始结果报告 SHA-256 `2f066cecd9f56036638469e680078dab095161d10504abc7cbbda28f99fbf5ab`，其 `ResultSummary` 为 1 次、0–1032 小时：`MTMF=0.8405485153`、`MSTF=0.8846153617`、`MSUF=0.7788461447`、`STMF=0.8405485153`。这些仅是 SIMLOX 候选结果，未映射为 canonical KPI。

原生 `-jsonreport` 会在数组结束前多写逗号；保留原始字节，[验证脚本](../../scripts/simlox/verify_j35_page_candidate.py)仅在内存中修复后解析。验证脚本同时检查 31 张表回导、组件/任务/库存数量、充氧工序只有 `PERSONNEL`、`DEVICE`、`P_MECH` 三类资源，以及结果的重复次数和时段。日志中的 0.47 秒是一次功能验证运行的程序计时，**不是与 #6 或 canonical 可比的性能基准**。

后续语义验收需要同一 J35 输入下的任务派遣、故障与维修事件、资源预约与等待、补给账本、随机请求顺序及输出分母；目前的聚合报告不提供这些逐事件证据。
