# 4700-3 P1 原生验收交接

2026-09-28 本轮更新：机主现允许经远程桌面操作 SIMLOX。原 Console-only
限制保留为历史交接背景；当前可在已核实的活动交互式 `Console` 或 RDP
用户会话中尝试 GUI 与原生运行。本交接的交互式 runner 拒绝 SSH/session-0。
机主另已允许以 SSH 做 CLI 模型验收；该路径必须有单独版本化的启动和来源
绑定，不能通过取消本 runner 的门禁或隐藏窗口来冒充 GUI 验收。RDP 可见
进程不等于许可证、导入和计算可用；首次
新运行须保留实际结果或失败现场。不要索取或记录登录凭据。

## 0. 先确认执行环境与证据边界

1. 在要启动 SIMLOX 的同一登录会话中先记录 `hostname`、
   `$env:SESSIONNAME`、`(Get-Process -Id $PID).SessionId`、`query session`、桌面
   可见状态、时间、工作目录及现有 SIMLOX 进程。确认同一活动交互会话后，才打开
   SIMLOX，记录 About/版本/许可证状态及可执行文件路径与 SHA-256。
   预期可执行文件为
   `C:\Program Files\Systecon\SIMLOX\Simlox.exe`，此前哈希为
   `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；
   实测不同时先报告，不按旧指纹强行执行。
2. 确认执行进程属于活动 `Console` 或 `rdp-tcp#...` 会话，且能看到实际桌面。
   如果没有窗口控制或截图能力，不得把 CLI 结果写成 GUI 已验收；明确列出
   缺少的窗口。现有 SIMLOX 进程或用户窗口不得被自动关闭或抢占。
3. 每个正式运行用唯一 run ID、新目录、冻结输入和来源哈希；一次只启动一个
   SIMLOX 作业。遇到活动进程，等待并报告，不抢占。原始运行目录及失败
   产物不覆盖、不重写。不要更改 A01/A02 冻结文件或旧证据。
4. 所有截图记录 UTC 或本地时间、窗口/表名、打开的文件路径、实际 GUI 菜单
   路径和文件 SHA-256。截图中的字段和值须清晰可读。

## 1. A01/A02 冻结复核与 GUI 校准

只读复核 `handoff-v1/manifest.json` 所列 A01/A02 各自的 final 和 replay
原始目录、输入/输出哈希与原有只读验证命令；复核 19 个冻结源文件与
`catalog-import-source-v2.json` 的哈希。GUI 先打开以下 final 运行的既有
`model.sxi`，再打开同目录 `model.sxo`；不要在原目录重新计算或保存：

```text
C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-final-20260927-03
C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-final-20260927-03
```

- A01：`Control` 1 次、36 小时、`ENLOG=Y`；`TEACH-AIR-01` 在
  `TEACH-UNIT` 部署 1 架；`BASIC-MISSION` 的 `NOS=MNOS=1`、持续 2 小时；
  `OperationProfile` 仅 08:00 一波。结果中通知 07:00、起飞 08:00、完成
  10:00，`SystemResults` 为 72 个半小时区间。
- A02：仍是同一架飞机；`OperationProfile` 为 08:00、20:00、32:00 三波，
  各 1 次；对应通知 07:00/19:00/31:00，起飞 08:00/20:00/32:00，
  完成 10:00/22:00/34:00。
- 两例均检查 `MissionPreparation`、`Item`、`TaskResource`、
  `StockAllocation` 无业务行；截图记录输入表关系、结果摘要、相关
  `SystemResults`。完整字段及既有哈希以 `handoff-v1/gui-checklist.json`
  为准。记录真实菜单路径，不凭表名推测 GUI 路径。

先给 A01/A02 各项写 `pass`、`fail` 或 `not_observed`，附原始证据。冻结
复核与 GUI 门没有通过前，A03 只能保留原有隔离探针地位。

## 2. A03 同编队两机：先看旧探针，再做正式新运行

父例门通过后，先只读打开这份保留探针的 `model.sxi` 与 `model.sxo`：

```text
C:\Users\user\Documents\Codex\2026-09-28\simlox-p1-a03-b7e6945a\cases\simlox-air-support\A03-two-aircraft-formation\runs\probe-a03-20260928-03
```

核对 `Control.APID=AIR_BASIC`、`NREPS=1`、`SIMPE=36`、`ENLOG=Y`；
`SystemDeployment.QTYPS=2`；`MissionType` 的 `NOS=MNOS=2`、`DURN=2`、
`NOPER=1`；`OperationProfile` 恰有 08:00 一波、`IQTY=1`、`DTIM=1/3` 小时
（20 分钟）。
准备、物料、任务资源和库存分配均无业务行。`MNOSA` 留空，不推断一个
独立的飞行中最低数量规则。

从结果窗口和原始 `model.log` 同时确认：一个任务身份
`<BASIC-MISSION,TEACH-UNIT,0,0,0>`；两架不同实例
`<TEACH-AIR-01,0>`、`<TEACH-AIR-01,1>`；同一次 08:00 起飞列出两架，
10:00 完成列出两架。`SystemResults` 显示 `NSYA=2`，08:00–10:00 的
`NSYMO=2`、`FTMO=1`。结论是**一波次、两架次**、4 飞机小时；`FTMO`
不是架次。结果摘要 `MSTF/MSUF=1` 也不能当架次数。

随后按 `A03-two-aircraft-formation/contract.json` 的输入哈希，在上述
活动交互会话用同目录 `run_native.ps1` 建立新的唯一 run ID，执行导入、回导、
计算、报告、严格验证及封存。本交互式脚本会拒绝 SSH/session-0，启动命令不再
指定隐藏窗口；保留 `invocation.json` 的会话 ID 和严格验证器哈希，以及
`strict-validation.json` 的摘要断言。再对**新** `model.sxi/model.sxo` 做同样 GUI
检查。脚本生成的 `run-manifest.json` 仍标记 `isolated_contract_cli`，
不能只改状态字段；正式结论须另写有父例、GUI、原始产物及独立复验绑定的
验收记录。保留旧探针与新正式运行各自的路径及哈希。

## 3. 通过父例和 A03 门后，再串行重跑 P1 队列

先从合并后的 `simlox/main` 在 4700-3 建立新的、记录 Git 提交和文件哈希的
执行快照，使用其中更新过的 `preparation-resource-v1/run_native.ps1` 与
`binding.py`。旧冻结源快照
`C:\Users\user\Documents\Codex\2026-09-27\simlox-preparation-resource-v1-6539ea720ef2`
仅供核对原始候选输入、manifest 和历史证据，不能用其中旧 runner 执行本轮。
新快照的 `native/manifest.json` 从 `candidates` 选取输入，并逐一核对它与
旧冻结快照的 `path`、`input_sha256` 完全一致。**不要选择** `failed_candidates`
中 B02 1.0.0 或 C01–C03 1.0.0。新旧源目录存在性、脚本位置及哈希均先实测。

按 `B01 → B02 → C01 → C02 → C03` 顺序执行；同一案例的所有活跃变体
逐项串行。B03 在 B02 通过后另列一项，不与资源链结论合并。可使用包内
`run_native.ps1` 的 `CaseId`、`VariantId`、`RunId`、`InputPath`、
`InputSha256` 参数，每项取新的 run ID。已有 12/12 是历史隔离 CLI
合同结果，不得直接晋级。

| 案例 | 必须核对的原生行为 |
| --- | --- |
| B01 | 07:30–08:00 固定准备；准备完成前不起飞。 |
| B02 | 10 分钟、20 分钟两工序严格串行；等待与作业分开。 |
| C01 | 正确资源 RID/数量；容量 2 可执行，容量 1/0 或专业不符时不得部分占用或开工。 |
| C02 | 人员和设备的申请、占用、释放均可逐项定位；设备为 0 时第二工序阻塞。 |
| C03 | 同任务两架逐架准备并共享人员；人员 2/1 对应整队 08:00/08:30 起飞，人员 0 不起飞并记录实际取消事件。 |
| B03 | `COLD-FIRST` 只执行 30 分钟冷准备，`HOT-SORTIE` 两波各执行 10 分钟热准备，同一飞机身份贯穿三波；不声称同 MTID 随出动历史自动切换。 |

每个变体检查导入/回导非空业务行一致、转换错误为 0、警告逐项解释，
原始 SXI/SXO/ENLOG/报告非空；按合同逐条核对任务、飞机、工序、资源
请求/等待/获得/释放及结束状态。GUI 截图要覆盖输入表关系和案例所需
结果窗口。资源事件不全时，即使汇总起飞时间符合，也不能签署 C03。
交互会话若拒绝 SIMLOX 启动或运行，保留错误、会话、许可证及启动上下文，
不要用旧 CLI 结果代替。

## 4. 交付给独立复验者

为每例/变体生成机器可读索引和简短结论，至少列：主机与交互会话
证据、SIMLOX 版本/哈希/许可证、源快照与输入哈希、父例状态、新 run ID、
GUI 实际菜单路径与截图 SHA-256、原始产物路径/大小/SHA-256、逐项断言
`pass/fail/not_observed`、首个差异及失败现场、警告解释。将原始产物
只读封存，把副本交给**未操作该运行目录**的复验者重跑断言；未取得独立
复验前标记 `pending_independent_review`。如 GUI 或前置缺失，最多报告
对应 CLI 范围，保持 `not_published`。

最后分别报告已实现、已验证、失败/阻塞、未验证与仍计划。C03 人员 0
在 08:30 取消只是该固定配置的观察；一般截止/取消规则另由 C04 验证。
P1 完成前不开展 108 例后续批次的发布验收。

阶段计划 P0 还列有 K01、K02、K07、J05；这些案例目前仍为规划状态。
上述 A01/A02 GUI 校准只补齐这条 P1 依赖链所需的父例门，不能据此宣布
整个 P0 阶段或工具案例发布完成。
