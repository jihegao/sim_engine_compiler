# J35 / SIMLOX 2017 逐事件对齐本机报告

本文件是 4700-3 Codex 原始 `evidence/final-report.md` 的仓库副本；原始字节 SHA-256 为 `329cb93b06bea7e6c788b873d28cea425b51b4cbe7b01261a8a0a2c5e2b8d7fd`。下文未带路径的证据文件名均位于该主机的 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\`；本工作树另在被 Git 忽略的 `data/local/simlox-4700-3-event-parity/` 保存报告及关键结果副本。原始日志、模型和全部哈希清单保留在 4700-3。

日期：2026-09-26；主机：4700-3；工作区为非 Git checkout 的固定 `3f24611` archive 展开件。**判定：Python/Rust 同 Plan 单样本通过当前跨后端语义范围；SIMLOX 与固定 J35 Plan 的全模型逐事件门槛未通过，故未执行 1000 样本同机性能实验，也没有速度比。**

## 来源、环境与原始文件

| 对象 | 本轮复核的 SHA-256 / 位置 |
| --- | --- |
| 源 zip | `b6096650ab8b38d1d867f2cd6a72f354180a901d2ff10c8e1caef90e40f14544`；父目录 `sim-engine-compiler-simlox-j35-3f24611.zip` |
| 固定 Plan | `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`；[`execution-plan.json`](../../tests/fixtures/spare_mvp/j35-amd128-0e709bd/execution-plan.json)；结构指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f` |
| canonical 输入 | `30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559`；同 fixture 的 `simulation-inputs.json`。仅使用既有 ProjectJsonExporter/SimulationAdapter 来源快照，未新增 Project JSON 解释器。 |
| 原始 SIMLOX 候选 | `.sxi` `1a8ab2f76171df4ca51a59879d06cd61ee8bd5aa9298a8761f6525a7308a9716`；`.sxo` `df2fdd03a40a16953ecf4b0ed7ab9027ffc54354d3b42a6420ff19a309128926`；报告 `8485b98ce8f13edb6cd7cefaa3168e64991be7d07263b08af87dd8d20ff76e1e`。均在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-page\`，本轮未修改。 |
| SIMLOX 程序及手册 | `C:\Program Files\Systecon\SIMLOX\Simlox.exe` SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；手册 `UserDoc\SIMLOX.pdf` SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`。既有来源记录报告产品版本 `2017.0.0.0`；本次 PowerShell `VersionInfo.ProductVersion` 返回空字符串，未据此改写既有版本说法。 |
| ENLOG 原生探针 | JSON `0b9a85290e49213a551b83247b4bada1882c0b583128c2d75ef44d85efde1df1`；首样本日志 `6fca1d0cbd1c75b7a8957c2fc364b7f4e784418c411f24d5fde02e59b84942b3`，8,183,455 字节。原件在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-enlog-probe\`，副本在 `raw/`。与主候选 JSON 的唯一业务字段差异是 `Control.ENLOG=N→Y`。 |

`environment.json` 记录 Windows 10 Pro `10.0.19045`、AMD Ryzen 7 4700U（8 核/8 逻辑处理器）、约 7.42 GiB 可见物理内存、Python 3.12.14、Rust 1.90.0 GNU 工具链及更多文件哈希。工具链、虚拟环境、编译产物和全部新模型均在 `evidence/`；原 SIMLOX 进程检查为空。Rust GNU release 程序为 `target-gnu/release/sim-engine-runtime.exe`，SHA-256 `f02a0cfd9261aa7817191fbf1d4d5d17b7a2d0fbc40882b30b67dfc7184730a1`。`commands.md` 保留安装、构建、运行命令和失败重试原因。

## 1. 同 Plan seed 1：Python reference ↔ Rust

Python 结果 `reference-seed1.json` SHA-256 `9ebe07f4a069fcc1f967f09ebb935a9e0537d45d13f8345fc9d2f76d66669a6a`；Rust 结果 `rust-seed1.json` SHA-256 `8b125045de79b92006491edccf4e0e891b2d2b6077cd5ca28baca4d22b24f7db`。两边 `plan_fingerprint` 均为固定值，`seed=1`、终止第 61464 分钟、`natural_complete`、trace 12,713 行；`trace`、`metrics`、`terminal_state` 和其余顶层字段逐字段完全相同。`sample_requests` 有 3394 条，其中仅 5 个 `value_minutes` 浮点值**精确不相等**，路径为索引 `[335]`、`[1315]`、`[1950]`、`[2000]`、`[3224]`，最大绝对差 `3.725290298461914e-09` 分钟；字段值和每项差额在 `seed1-exact-diff.json`。未把末位差异隐藏为“完全相同”。

Rust 单次 `--profile-output` 给出加载 14.3064 ms、初始化 11.7856 ms、执行 473.6134 ms、结果写入 35.1607 ms、进程内墙钟 540.1452 ms；这只是一次功能运行的分段背景，未预热/重复，不是性能结论。Python 运行需 `PYTHONUTF8=1`；未设置时 Windows GBK 解码 Plan 失败，见 `reference-gbk-attempt.log`。

## 2. ENLOG 提供的事件证据与边界

手册印刷页 233 明确 `Control.ENLOG=Y` 输出首个重复样本的完整调试日志至同名 `.LOG`，本机 PDF 文本核对见 `manual-enlog-search.json`。原生 ENLOG 有 110,437 行、70,851 条 `Time:` 行，覆盖打印 `0–1032` 小时；`extract_enlog.py` 明确分类 30,503 行至 `native-selected-events.jsonl`，包括后续缩进行的故障部件、资源数量/可用性及欠交数量。原始日志完整保留；“完整调试日志”不等于所有语义都有与 Rust 相同粒度的结构化事件或 RNG tape，见 `event-mapping.md`。

同一业务波次的**候选序位映射**由 104/104 个原生创建时刻与 Plan 的准备时刻一致支持。飞机 `<J35,n>` 是原生实例序位，不能无条件绑定稳定尾号。日志 `Time:` 小时文本以可变小数位打印；跨引擎比较只在可手算的首波工序上使用 ±0.001 分钟打印容差，随机故障时刻没有据此判为同一事件。

### 可控差异和验证过的确定性切片

原主候选的**首个确定性资源差异**在 `Time: 5.13333 h`（打印值约第 308 分钟）：起飞前第 2 工序对每架飞机除通用 `PERSONNEL×1`、`DEVICE×1` 外还预约 `P_MECH/P_ARM/P_SPEC/P_AVION` 各 1；固定 Rust Plan 只预约通用各 1。原生附加约束是页面专业需求与 Plan 通用需求的叠加，不能称为同一资源模型。

隔离受控模型 `simlox-control/j35-generic-resource-control.json`（SHA-256 `fc1a0be984258d3f65a7fc97b9addfee78f23583598dd97552e39cc0c4ff2bbc`）仅移除 27 条起飞前专业资源需求，其他 JSON 字段相同；导入、回导、运行退出均为 0，原生 ENLOG SHA-256 `5a3bdbb9e969b2f3a80b5dc9e72bbfed06cd8cec563285fa7f217fa3b4ef4038`。与主候选相比，seed 1 的 6714 条已分类非资源行和只保留通用资源数量/可用性检查后的 20343 条行序列均相同；说明当前容量下专业覆盖未改变这些投影事件，但**预约语义本身不同**。

在受控模型中仅将 `Control.RSEED=1→2`（模型 SHA-256 `33491ddd14b9ae15828d3d3b08012041d4506c9e4d846b1f3f4754ccedfafb6f`，日志 SHA-256 `dfe0950b7dce879cfbed4260aa6b4d4a51c3e081ac1b46d09fffe83d1b9a9d91`），两原生样本至第 600 分钟的 801 条选定事件一致；Rust seed 1/2 同期 463 条 trace 一致。首波两机 14 步共 56 个起止时刻与 Rust 的对应步骤均在打印容差内，通用人员/设备的第二步请求数量也对上。证据为 `deterministic-prefix.json`、`first-preflight-control-comparison.json`。这是**无已观察故障的准备/起飞切片**，不代表隐藏随机请求相同，更不代表全模型等价。

### 首个结果分歧及后续缺口

主候选与固定 Rust seed 1 均在第 600 分钟启动候选序位 2 的波次。原生 `Time: 10.4767 h`（由打印值换算约第 628.602 分钟）记 `<J35,5>` 的关键随机故障，后续行指出 `<J35-PART-2602030200000799,0,501>`，并中止该波；Rust 的同序位波次未故障，于第 843 分钟通过成功点。Rust 首个组件故障在第 3611 分钟，为另一尾号/部件。原生关键故障 19 次，Rust 组件故障 10 次；相同数字种子不构成同一随机流。候选波次匹配在 `mission-candidate-matching.json`：104 波创建时刻匹配，85 波起飞时刻或双方均未起飞匹配，71 波成功布尔值匹配；首个起飞有无差异在序位 19。

PM 差异独立于资源覆盖：原生首个 PM 启动约第 10884 分钟、总 48 个；Rust 首个 `preventive_created` 在第 1440 分钟、总 58 个。原生模型没有表达固定 Plan 的 7 日历天或 25 飞行小时复合触发与逐机初始寿命。原生 19 次系统送修、33 次物项维修开始、33 次物项需求、32 次新增欠交；Rust seed 1 只有 10 次 `repair_completed`，`spare_demand_total=0`、`shortage_events=0`。这些计数含义和触发路径各异，不能逐项相减归因。原生日志没有可配对的基地→基层物项转运开始/到货事件，`check for return transport` 是人员/设备返程检查，不能代替库存转运证据。

观察终点也不同：原生日志至 1032 小时（61920 分钟），Rust 第 61464 分钟自然完成，比原生上界早 456 分钟。原生 `mission success` 在完成时记日志，未提供可直接对应 Rust 起飞后 0.75 时点的成功判定行。随机调用、连续小时/整分钟排序、预约、CM/库存与结果口径均未通过全模型门槛。

### 原生起飞前排队与 DTIM 事件实验

另外从既有隔离模型**各只改 `Control.ENLOG=N→Y`**生成两份 `P_ARM=1` 事件探针。`DTIM=20` 模型 JSON SHA-256 `295066089590afc9e0ee7edd3f387f80837248b8a2439fdfa86213b05a4bf5f0`，日志 SHA-256 `99d4c9f081d65deb9335cffd83d77d8379a7598f00cd6739e2cf45815f0c0c6e`；`DTIM=NULL`（手册默认 0）模型 JSON SHA-256 `97226d18d4acb4041248264e642e9699c8fe3b4dba624813fd605edac938b755`，日志 SHA-256 `1a06fcfae1b18ee2edccbf24eba4f7faa180578c1f0fdc5ba5e75872f46010f6`。四个关键表原生回导行与输入全等，见 `roundtrip-verification.json`。

20 分钟窗日志中有 4070 次 `P_ARM` 数量 1 的可用性检查失败，26 波开始、78 波取消；其中 77 波在打印精度内约于计划时刻后 20 分钟取消，另 1 波在计划前约 121.98 分钟取消（原始第 82007 行，需单独调查原因）。零窗口日志有 3722 次失败检查、12 波开始、92 波均在计划时刻取消。失败检查是**重复重试次数**，不是独立排队事件数；两模型均未观察到实际延后起飞。原生资源排队与取消时刻可见，但与 Rust 固定 Plan 的专业资源设置不同，不能宣称跨引擎 DTIM 等价。

## 3. 语义门槛与性能结论

明确的进入条件：同一业务模型及逐机状态；同一可释放资源、库存与运输事务；可控故障/PM 外生事件或经验证的随机请求合同；任务通知/准备/起飞/取消、故障、维修、人员设备等待与释放、库存请求/到货、停止状态逐事件且数量匹配；输出分母、成功判定和观察终点一致。时间比较应定义原生打印精度、分钟量化及同刻排序规则，不能用行号或近似汇总代替。

**目前未达上述门槛。没有执行 1000 样本、预热、三轮或跨引擎速度比。** `ENLOG=Y` 只用于事件调查；已有单次原生功能日志的 1.18 s 仿真 / 1.33 s 总时间与无日志的 0.35 s / 0.47 s 不可当性能比。以后若语义验收通过，需在 ENLOG=N 下固定模型/样本集合、线程数与报告级别，分别记录预热及至少三轮加载/准备、初始化、执行、保存/导出、端到端和机器负载，并确认 SIMLOX `NREPS=1000` 与 Rust 1000 samples 的统计单位及进程启动边界一致。

## 下一步（需解决的具体技术问题）

1. 从 Business IR/canonical 来源确定目标资源模型：是保留页面专业约束并在两边完整表示，还是统一为 Plan 通用容量；不得直接改固定 Plan 文件或把受控 SIMLOX 模型称为原 J35。
2. 为 SIMLOX 构造能重放确定性故障、PM、维修和补给的小样本，核对它是否提供固定外生故障/寿命输入；同步确认原生聚合部署如何承载逐机稳定身份与初始寿命。若不能表示复合 PM/身份/库存事务，记录为 SIMLOX 能力缺口并降低验收范围。
3. 定义连续小时到 `legacy-minute-v1` 的事件时间和同刻顺序合同，校准任务成功点与自然停止；重跑全类事件差分。只有通过上述门槛后，按 `commands.md` 所述建立 1000 样本分段基准。

## 文件索引

- `environment.json`：本机版本、CPU/OS、源文件及执行文件哈希。
- `commands.md`：安装、构建、运行和探针命令；`cargo-build*.log`、`rustup-*.log`、`raw/` 及各 `simlox-*` 目录保存原始日志。
- `seed1-exact-diff.json`：Python/Rust 全 JSON 路径级差异；`reference-seed1.json`、`rust-seed1.json` 为原始结果。
- `native-selected-events.jsonl`、`native-selected-events.summary.json`：ENLOG 明确识别的行、后续字段、计数；原始字节在 `raw/j35-page-enlog-probe.log`。
- `event-mapping.md`、`mission-candidate-matching.json`：字段映射、首个实质差异、逐波候选配对。
- `simlox-control/`、`simlox-control-seed2/`、`simlox-arm1-enlog/`、`simlox-arm1-zero-enlog/`：受控模型、回导、原生运行与逐事件审计。四组均为隔离复制实验，不能和固定主候选混称。
- `file-manifest.json`：可审阅证据文件的字节数及 SHA-256。
