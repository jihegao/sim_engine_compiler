# F35 43 天 SIMLOX 候选模型

状态（2026-09-26）：4700-3 上的 Codex 已建立一个**可运行的结构对齐子集**，不是与 `spare_mvp` 等价的模型。原生导入、`.sxi` 保存、`-jexport` 往返和一次仿真完成；最后一次输入转换报告 0 错误、0 警告、0 提示。未通过逐事件语义验收，不据此比较效率。

## 身份与原始证据

- 独立工作目录：`C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-model`。本机只读副本：`data/local/simlox-f35-model/`（Git 忽略）。Windows Codex CLI 会话：`01a0dbb3-947b-78e1-abfa-9e05e79bc70f`。
- 固定 `simulation-inputs.json` 字节 SHA-256：`a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`；上游提交及 Plan 指纹见[来源对齐记录](README.md)。SIMLOX 2017 程序 SHA-256：`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；原生模型数据库版本 `20160627`。
- 候选 `models/f35-candidate.sxi` SHA-256：`4a89200e4d05ee78a18ccee0a00f19d5c273717f6815b67d894ea85fc7b3438a`。同一工作目录保留生成脚本 `build.js`、候选 JSON、原生回导 JSON、原生 `.sxo`、未经改写的结果 JSON、`verify.js`、`models/verification.json`、`models/f35-run5.log`、`MAPPING.md`、`COMMANDS.md` 和 `SHA256SUMS.txt`。逐文件哈希和命令关联以这些原始文件为准。
- 本机复制后重新计算五个主要模型和结果文件的 SHA-256，均与原机 `models/verification.json` 的记录相同；`issues=[]`。

## 已核对的结构与运行

| 项目 | SIMLOX 原生回导中的行或值 | 限制 |
| --- | --- | --- |
| 期限、样本与收集间隔 | `SIMPE=1032` 小时、`NREPS=1`、`RCINT=0.5` 小时 | 时间换算和数量一致；输出指标分母未对齐。 |
| 飞机和部件 | 1 个 `System.F35`、9 架部署、423 个非根 `Item` 与 423 条 `ItemStructure` | 无逐机尾号和初始寿命状态。 |
| 任务 | 1 条 `MissionType`、104 条定时 `OperationProfile` | 104 个起点与 canonical 的 26 日 × 4 波次相同；派遣和取消规则不同。 |
| 维修与 PM | 423 条 `ItemRepair`、2 条 `MaterielPM`、2 条 `PMLocation` | 维修工序被简化；7 天或 25 飞行小时的复合 PM 触发未完整表达。 |
| 资源与库存 | 40 人、60 台设备的汇总容量；167 条正库存 | 工种、设备类型、步骤竞争、换件消耗和运输未表达。 |

最后一次运行日志 `models/f35-run5.log` 明确写出该 `.sxi` 的输入和同名 `.sxo` 输出，转换 0 错误/警告/提示。`-jsonreport` 从这份 `.sxo` 导出 `models/f35-result-raw.json`；结果摘要为 1 次重复、0–1032 小时。原生报告存在数组末尾多余逗号；验证脚本只在内存中清理，保留原始字节。

## GUI 核对

在 4700-3 的 Windows App 远程桌面中，使用 SIMLOX 的 **File → Open** 对话框逐级进入上述 `models` 目录，打开 `f35-candidate.sxi`。SIMLOX 窗口标题显示 `f35-candidate.sxi`，`ProblemDescription` 表显示 “Pinned spare_mvp F35 43-day case; approximate SIMLOX mapping; see FINAL.md”。这是原生 GUI 能打开该文件的独立核对；没有在 GUI 中运行仿真或逐表人工核对全部记录。Windows Codex CLI 自己的 Computer Use 会话未列出窗口，其 `FINAL.md` 中“不主张 GUI 验证”仅指该 CLI 会话；本段记录的是本任务另行完成的远程桌面核对。

## 仍未对齐

SIMLOX 拒绝 canonical 种子 `0`，运行候选使用 `1`；故障率按每运行小时解释，且为满足 SIMLOX 母件约束重写了父件 `FRT`。任务的 `daily-v1` 预约、取消、阶段、返场与再次出动，作业 DAG 和采样时长，直接维修与换件选择、预防维修初始寿命、类别化资源竞争、库存事务、随机请求 tape 和输出分母均未证明等价。完整逐字段表见[候选模型映射表](f35-candidate-mapping.md)；原始文件为原机 `MAPPING.md`。当前结果只能证明此**近似候选**可运行，不能当作 canonical F35 对照结果。

4700-3 上对该候选模型的单样本与批量计时见[F35 候选模型效率记录](f35-candidate-benchmark.md)。
