# 4700-3 J35 合同探针结果（2026-09-27）

**验收结论：未通过完整 J35 语义门槛。** 协调端在正常 SSH PowerShell 启动上下文中运行了首版 12 格与修正 PM 实际时长的 8 格有效原生取消探针，以及最终六格有效一件备件/维修探针；旧版“SIMLOX 软件不可运行”的断言已撤回。首版取消矩阵误将 `PMLocation.PMT` 当成 PM 实际时长，修正八格通过 `TaskBreakDown.DURN` 判别第二架临界可用时刻。备件探针的前两轮严格拒收并保留：`p2-*` 回导 `RSEED` 类型不全等，`p2b-*` 原生转换错误 `#2050` 且 SXO 仅 4 字节；最终 `p2c-*` 恢复源模型合法的 FRT 层级。保留 phase7 第 20 波确定性取消反例；没有改固定 Plan、Python/Rust、旧候选或 phase1–7 原始证据，没有新 1000 样本或速度比。

## 1. 来源、隔离与可复现环境

完整 Git bundle 克隆的起点为 `526820f4631ceeb7c732f24b8a1c3e0cabcbea97`（分支 `codex/simlox-semantic-alignment`，祖先 `e9b6391fffd918e0f6e742bd1ef0e1312921b769`），本工作分支 `codex/simlox-j35-contract-probes`。逐项指纹见 [来源 manifest](j35-contract-source-manifest.json)。AMD128 `spare_mvp` 上游修订为 `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`，canonical 输入沿既有 `integrations/spare_mvp`；没有新增 Project JSON 解释器。固定 Plan 字节 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，内含指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`。

Windows 新 clone 曾受全局 `core.autocrlf=true` 影响，Plan 工作树换行为 CRLF 而 Git blob 正确；本 clone 仅设置本地 `core.autocrlf=false` 并从自身 Git blob 恢复三个 J35 fixture 原字节，索引无差异。原始模型与旧证据仍在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\phase1…phase7`，只读复用。全部本轮模型、命令结果和大文件在被 Git 忽略的 `data/local/j35-contract-probes/`；`git check-ignore -v` 证实 `/data/local/` 生效。SIMLOX 每次调用前检查进程，未终止或占用用户 GUI。

复用隔离 Python 3.12.14 / SimPy 4.1.1。重新以 Rust 1.90.0 GNU、`--release --locked --offline` 从本 clone 构建，工具链与缓存均在旧用户工作区 `evidence/`，新构建输出只在本 clone `data/local/`。[构建脚本](../../scripts/simlox/rebuild_j35_rust.ps1)与本机 `data/local/j35-contract-probes/p0/rust-rebuild/result.json`、`cargo-build.log` 可核验；新 exe SHA-256 `eeaf9a437e3b12cc18402a0045dbe105008acdf975b2b29a2e310e1fe09c1ef4`，旧 exe `f02a0cfd9261aa7817191fbf1d4d5d17b7a2d0fbc40882b30b67dfc7184730a1`。两 exe 字节不同但同 Plan seed1 的完整 RunResult **逐字段相同**，见 `p0/rust-rebuild/old-new-rust-diff.json`。本次单样本运行不是性能测量。

固定 Plan seed1 的 Python 与新 Rust 都得到 `time=61464` 分钟、`natural_complete`、12713 条 trace、相同 Plan 指纹；`trace`、`metrics`、`terminal_state`、`seed`、`time`、`stop_reason` 完全相同。[精确比较脚本](../../scripts/simlox/compare_j35_run_results.py)仍发现 5 个 `sample_requests[*].value_minutes` 浮点末位差异，索引为 335、1315、1950、2000、3224，最大绝对差 `3.725290298461914e-09` 分钟，原始清单在 `p0/rust-rebuild/python-rust-diff.json`。因此「主要可观察输出相同」已验证，「完整 JSON 位级相同」不成立。

## 2. P1：有效原生矩阵与纠错

旧 `evidence/phase7/report.md` 所记的八 SID PM-only 20 波前 19 波对齐，第 20 波无随机故障：原生在 `176.967 h` 取消并中断第 8 步准备、释放资源，固定 Python/Rust 在 `179 h 20 min` 取消。它与 `STIM+DTIM−142 min` 计算一致，但只支持候选解释，不证明通用动态可行性算法。完整 PM-only 原生 88/104 起飞、Rust 89/104；这不是 RNG 差异。phase7 完整原始日志、首差、回导与哈希仍在旧证据目录。

[矩阵生成器](../../scripts/simlox/make_j35_cancel_matrix.py)从 phase6 已验证的两稳定 SID 模型（SHA-256 `ec93b454aceb58a6fb49f47fe1e16064ffb21a9e699c785fea39276c7e4c6b17`）派生首版 12 个隔离 JSON。协调端将其逐个复制到 `data/local/j35-contract-probes/coordinator-p1-*`，再从旧 workspace 工作目录调用原生 runner。每格 `jimport/jexport/calc/jsonreport` exit 0、转换 `Errors: 0`、SXO 约 616 KB、30 个非空业务表回导全等，完整 ENLOG 与报告在各目录。逐格指纹、有效性、行号和摘录由[分析脚本](../../scripts/simlox/analyze_j35_cancel_matrix.py)生成于本机忽略目录 `p1-native-analysis.json`。

**首版设计错误已确认：** `p1-before/tie/after` 等格改的是 `PMLocation.PMT`，真实 PM `TaskBreakDown(PM_25H).DURN` 仍是 24h。所有 12 个日志都在 24h 启动 PM、48h 完成（`coordinator-p1-before` 第 258/346 行），53h 通知时两架都已 ready（第 350–361 行）。因此这些格虽是有效原生模型，却不是“第二架在候选截止前/同刻/后恢复”的有效判别。修正的 `p1v2-*` 八格改变实际 PM 步骤时长并保留 `PMLocation.PMT=24h`；协调端已逐格得到四步 exit 0、转换 0 错、非空表回导全等和有效 SXO。逐项输入差分、SHA、完整 ENLOG 和命令在被 Git 忽略的各同名目录；机器可读分析为 `data/local/j35-contract-probes/p1-native-analysis.json`。

| 修正格（输入 SHA-256 前 12 位） | PM 完成 h（日志行） | 首任务结果 h（行） | 判别 |
| --- | --- | --- | --- |
| `p1v2-pm-before` `2ab8abfd37b8` | 53.95 (558) | 起飞 56.3167 (1126) | PM 在 53.9667 截止前完成 |
| `p1v2-pm-tie` `048f88fe3c77` | 53.9667 (594) | 取消 53.9667 (546) | 同一打印时刻先记取消 |
| `p1v2-pm-after` `39b87f1402d5` | 53.9833 (594) | 取消 53.9667 (546) | 晚于截止 |
| `p1v2-pm-dtim40-before` `d8482db95ca0` | 54.2 (585) | 起飞 56.5667 (1126) | DTIM=40 分钟时截止 54.3 |
| `p1v2-pm-dtim40-after` `66cfc51a10ed` | 54.4 (621) | 取消 54.3 (573) | DTIM=40 分钟时晚于截止 |
| `p1v2-pm-step-short` `b09f1a276962` | 54.2 (612) | 起飞 56.2333 (1126) | 准备缩至 122 分钟，截止移至 54.3 |
| `p1v2-zero-before` `c270926623de` | 56.3167 (366) | 起飞 56.3167 (391) | 准备为零，截止 56.3333 |
| `p1v2-zero-after` `ff5b0a7102c` | 56.35 (385) | 取消 56.3333 (354) | 准备为零，晚于截止 |

八格日志的 `mission waiting` 都直接打印超时值，数值在打印精度内符合 `STIM+DTIM−总准备时长`。同刻格只证明日志顺序；不能以有限小数认定内部浮点精度或普遍事件优先级。[可审阅事件索引](j35-cancel-matrix-evidence.json)保留 20 格完整输入/ENLOG/SXO SHA-256、有效性、PM 完成和任务结果行号；索引 SHA-256 `0e32f97378bad3a2f65caf4553ef4a6191fe8eb5587271a25bd1c76ab0eab65c`，可用 `analyze_j35_cancel_matrix.py --summary docs/simlox/j35-cancel-matrix-evidence.json` 从原始日志重生。

仍有两条局部可复核的规则证据。`coordinator-p1-resource-one` 输入 SHA-256 `9bc0c5950140355f4d2005cdd6f5958e695a17bbd390582ead21e98ba560bb5d`，ENLOG SHA-256 `6dcae208a85475271928351fd75f32eb4f3c703c4c78c783e4a7a40abbbe5ff2`：53h 已分配 A/B（ENLOG 第 353–361 行），B 因共享人员/设备各 1 在第 380–381 行无法开始首步；A 于 55.3667h 完成，B 继续准备，到 `56.3333h=STIM+DTIM` 才取消（第 971–989 行），当时 B 正在第 8 步，停止并释放资源。这**排除**“只要全部准备赶不上就一律在 `STIM+DTIM−总准备时长` 取消”的通用规则。`coordinator-p1-next-wave` 输入 SHA-256 `72e12e0ef921eb62e179e163063f21b079bb192201c882635ab3c60e71af598d`，ENLOG SHA-256 `30d000cb15ec5b8910c56dfa9bb521bde85027c5cdc1ea89aee951cbf3bcc442`：第二波计划 57h、通知 54h（第 769–772 行），两架仍被 56h 第一波占用；日志明写等待超时 `54.9667h`，该波第 1043 行取消，第一波继续准备并在 56h 起飞（第 1140 行）。该超时符合 `57h+20min−142min`，支持**尚缺飞机时**的最迟启动门槛，仍需修正版在第二架真正临界返回时检验同刻排序、零准备与 PM/资源释放优先级。ENLOG 的小时打印约 4–6 位有效数字，不将小数末位当精确算法。

[原生运行脚本](../../scripts/simlox/run_j35_native_probe.ps1)逐步要求输出存在、非空业务表回导全等、转换 `Errors: 0`、SXO 大于 4 字节。**启动上下文差异：**当前 Codex 命令执行上下文中，原 `p1-before` 导入和已知有效 phase7 SXI 回导均 exit 0 而没有文件/日志；即使在 runner/直接子进程中显式指定旧 workspace 为工作目录，也复现无输出。原始失败记录在 `p1-before/steps.json`、`preflight-direct/result.json`、`preflight-working-dir/result.json` 和 `p1-stim-earlier/steps.json`。但协调端使用同一个 exe、同一已知 SXI，经正常 SSH PowerShell `Start-Process -WindowStyle Hidden -WorkingDirectory <旧workspace>` 成功得到 1,610,194 字节 JSON 与 Export completed 日志，见任务目录 `coordinator-preflight/`；随后同一外部上下文调用**同一 runner**使 `coordinator-p1-before` 和其余 11 格有效运行。程序指纹未变、模型不是无效；两条路径的用户会话/令牌/进程上下文具体差异尚未独立定位，不能归咎于工作目录单因子或软件许可。当前 Codex 为 `4700-3\\user`、Windows session 1、PowerShell 5.1；协调端 SSH 的有效进程 session/令牌尚未记录，不能据此断言权限原因。

已验证缺机临界 PM 返回、零准备、DTIM 与步骤时长改变、资源竞争和紧邻后续波次的上述切片。尚未完整覆盖准备/PM/资源释放**精确同一内部时间**的优先级及所有队列状态；也未重建完整 104 波的等价取消规则。不得把起飞总数当作这些规则的证据。

## 3. P2/P3：403 LRU 与可观察库存账

[逐件静态映射](j35-lru-static-mapping.csv)和 [汇总](j35-lru-static-summary.json)从固定 Plan、canonical 输入生成并先验哈希校验；403/403 个明确 LRU 有唯一源路径、组件/产品 ID、父链、每机安装槽、8 尾号、失效率/失效阈值、修理活动、人员/设备、时长、共享库存和运输路线。深度 2 为 167 个、深度 3 为 236 个；**没有直接挂系统根的 LRU**。每个产品有八个安装槽，合计推定 3224 个装机槽；这不是 3224 种库存品类。另有 20 个未标型中间件，均有正失效率。Plan 仅有两处共享库存池，基地初始 501 件、上级初始 0 件，单条容量 1、120 分钟运输路线；基层共享人员 40、设备 60，未按八 SID 复制。

固定 Python reference 中，失败组件引发 `replacement` 且该活动无静态备件时，按失败 **LRU 产品 ID** 注入数量 1 的备件需求；父链用于根部失效传播，修复完成重抽该组件寿命。Rust 对应路径已核查。该执行语义支持「失败的嵌套 LRU 自身是请求的产品」，但 canonical 父关系没有独立写明实际拆装边界、拆下坏件归属及维修回流，不能由嵌套结构断言父件仅聚合。SIMLOX UserDoc 印刷页 241/247 和字典区分系统一级 LRU/PRU/DU 与车间二级 SRU/SPRU/DP；把 403 LRU 转为二级件会改变领件和回流事务，phase6 的 PRU→SPRU 能力探针不证明无损。

本轮没有把 MTBF 常数冒充固定故障时刻。[P2 输入生成器](../../scripts/simlox/make_j35_stock_repair_probes.py)从 phase6 已验证的 PRU→SPRU 零库存修理模型（JSON SHA-256 `1b01a20111aed6c6fc96339c512147c862178967c01e67421eb380379b45f8d0`）生成单机/两机、启用/关闭非零 2h 二级直接修理的隔离模型：仅 BASE 有 **1 件共享顶层 PRU 现货**、DEPOT/二级现货为零、无自动订货；`RSEED="1",NREPS=1,ENLOG=Y`。两份完全同输入重复模型用于验证原生首样本故障/需求时间线可复现，不把相同 seed 当成 Rust 共享随机流。两机 `QTYPS=2` 的实例序号仅供此能力试验，不能映射为固定 J35 尾号。首轮 `p2-*` 六格导入/回导退出 0，但数字 `RSEED=1` 在原生回导成为字符串 `"1"`，非空表未全等，runner 按门槛在仿真前停止。第二轮 `p2b-*` 修正字段类型、回导全等，但将系统和顶层母件 `FRT=0`、二级子件保持正值，原生转换逐格报两条错误 `#2050 Mother with FRT = 0 has subitems with FRT > 0`，SXO 均仅 4 字节，严格判为无效。两轮原始模型、步骤与错误仍在隔离目录。第三轮 `p2c-*` 恢复 phase6 来源的母子 FRT=4000000，保留共享一件备件与修理开关；**六格均四步 exit 0、转换 0 错、非空表回导全等，SXO 约 575 KB**。每项差分、SHA、完整 ENLOG 和输出在同名目录。[可审阅物料事件索引](j35-stock-repair-evidence.json) SHA-256 `1449d0aa4a5f32e3a0f5c1c875a0cb1eb554750ddb736a95ee5f83c456191eb1`，由[事件分析脚本](../../scripts/simlox/analyze_j35_stock_repair.py)从有效原始日志重生。

两机同一随机输入的首两次**实际发生**故障在 `8.14122h`（`J35,0`，日志第 976 行）和 `8.23494h`（`J35,1`，第 982 行），均打印为顶层 PRU 失效；这是原生复现结果，不是输入的显式故障时刻。`8.28243h` 第一机从 BASE 取走唯一顶层备件 `<B-TOP-PRU,0,0>`（第 1012–1014 行），第二机的顶层需求形成欠交（第 1033 行）。二级件又在 `9.78243h` 形成两条欠交（第 1098、1117 行），显示车间层交易。开启二级直接修理时，二级件在 `13.2824h` 完修、到货并解除欠交（第 1194–1204 行）；顶层坏件在 `14.7824h` 完修回流，第一件解除第二机欠交并被其维修任务领用（第 1244–1249 行），第二件入 BASE 现货（第 1263–1265 行）。其后该实物 `<B-TOP-PRU,0,3>` 于 `32.2584h` 再被取出（第 2173 行），证明有回库后再领的原生路径。关闭修理时，唯一初始件仍在 `8.28243h` 被第一机取走，但顶层与二级欠交无解除、无完修回流；后续任务在 `29.9667h`、`53.9667h` 取消（第 1466、1767 行）。同一输入的两份 repair-on 副本有相同输入 SHA 及所选事件全时间线；原生 ENLOG SHA 也相同。修理开关改变后未来故障数量不同，故只对开关前的相同前缀和各自条件路径作因果判断，不伪称两配置共享完整故障 tape。

该探针**验证 SIMLOX 原生一级换件、一件共享现货争抢、欠交、二级修理、顶层回流及复领能力**，未验证这条 PRU→SPRU 物理交易与固定 J35 的嵌套 LRU 相同。固定 Python/Rust 在失败 LRU 产品的 replacement 活动中直接请求该 LRU；Plan 不完整暴露拆下坏件、车间二级交易或装机/在修实物账。两端目前没有同一可控故障事件注入与可比完整实物状态，故不能将上述日志按行等价于 Rust trace，也不能据此验收 403 件全模型守恒。

既有可执行 Python `b3-upstream-transport` 样本测试验证一次请求、一次运输、一次消费，初始现货 = 期末现货 + 消费量；这是**单端、可观察库存账**。完整 J35 的装机好/坏件、预留、在修、运输、报废、外流及维修回库并未全部作为同义原生/Rust 状态暴露，故实物守恒和需求守恒尚未验收。终点欠交不能算实物。即便新 P2 能证明原生一级/二级换件、共享争抢与回流，也仍需上游逐产品物理换件边界与共同故障注入，才能比较固定 Plan 的 403 LRU。

## 4. 状态、门禁和复现

| 类别 | 实际结论 |
| --- | --- |
| Implemented | 来源锁定计划/manifest；首版十二格与修正八格取消输入、P2 六个一件现货/修理输入及逐字段差分；严格原生有效性和 ENLOG 行号分析脚本；403 件静态映射；逐字段输出比较器、回导核对器、离线 GNU 重建脚本和行为测试；[独立合同提案](j35-common-contract-proposal.md) |
| Verified | 固定输入哈希；新 Rust 与旧 exe seed1 全输出相同；Python/Rust seed1 仅 5 个采样浮点末位不同；403/403 LRU/共享池静态覆盖；协调端 20 格有效 P1 与 6 格有效 P2c 原生运行；缺机 PM 临界返回、等待截止随 DTIM/准备时长移动、已选齐资源竞争末窗取消；一件顶层备件争抢、欠交、二级修理回流和复领的原生局部路径；同输入原生重复事件一致；phase6 零库存修理旧日志与 Python 最小运输单端库存账 |
| Unverified | 内部精确同刻优先级及取消规则的完整状态空间；403 件源物理换件边界；共同可控故障、完整 CM/库存实物与需求守恒；完整 104 波 PM-only、故障/资源/任务/停止及可比输出；独立 RNG 分布验收 |
| Blocked for full parity | phase7 第 20 波固定合同与原生取消时点不一致；403 LRU 不能无证据地重分类为二级件。新原生运行须用已验证可用的协调端 SSH 上下文；当前 Codex 子进程无输出的根因未定位，但不是 SIMLOX 普遍不可运行。 |

运行针对性测试：`python -m unittest discover -s tests/conformance -p test_j35_contract_probes.py -v`，本机 13/13 通过，其中旧/新原生日志和本地矩阵测试在非 4700-3 环境会明确跳过。可重跑顺序：先用 `scripts/simlox/rebuild_j35_rust.ps1`、`scripts/run_reference_plan.py` 和 Rust exe 跑固定 seed1；用比较器保存精确差异；用 `scripts/simlox/audit_j35_lru_contract.py` 重生映射；用两个 `make_j35_*probes.py` 生隔离输入；在有效外部 PowerShell 上下文逐格用 `run_j35_native_probe.ps1 -Stem <stem>`，再用两个 `analyze_j35_*` 脚本保存带行号的原生分析及 `--summary` 可审阅索引。生成器拒绝覆盖已有模型；新目录需隔离复制或全新工作树。本次本地 `data/local/` 保留所有原始输入、`provenance.json`、有效/失败步骤、完整 ENLOG 与构建输出，不纳入 Git。

完整 PM-only 前 20 波已发生确定性事件分叉；P1/P2 局部原生能力虽已判别，却未给出保持固定合同的无损完整 J35 模型，也没有相同的可控故障/完整实物账。因此未预注册新候选分布、未复跑 1000 样本、未做同边界性能计时或给出加速比。旧候选 1000 样本只作历史诊断。后续须独立解决取消合同、403 件物理换件边界，重验 104 波、共同窗口/终态和输出；只有通过这些门槛，再事先确定独立样本的指标、业务容限、方差/样本量与区间方法。未批准的容限或普通 `p>0.05` 不能证明等价。
