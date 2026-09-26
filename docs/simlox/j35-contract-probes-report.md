# 4700-3 J35 合同探针结果（2026-09-27）

**验收结论：未通过完整 J35 语义门槛。本轮完成来源锁定、Python/Rust 复跑、403/403 LRU 静态覆盖和原生取消矩阵输入；新增原生矩阵未能运行。** SIMLOX 2017 CLI 在本会话对既有有效 SXI 也退出 0 但未生成 JSON/日志，不能把退出码或生成的 JSON 候选算作原生验证。保留 phase7 第 20 波确定性取消反例；没有改固定 Plan、Python/Rust、旧候选或 phase1–7 原始证据，没有新 1000 样本或速度比。

## 1. 来源、隔离与可复现环境

完整 Git bundle 克隆的起点为 `526820f4631ceeb7c732f24b8a1c3e0cabcbea97`（分支 `codex/simlox-semantic-alignment`，祖先 `e9b6391fffd918e0f6e742bd1ef0e1312921b769`），本工作分支 `codex/simlox-j35-contract-probes`。逐项指纹见 [来源 manifest](j35-contract-source-manifest.json)。AMD128 `spare_mvp` 上游修订为 `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`，canonical 输入沿既有 `integrations/spare_mvp`；没有新增 Project JSON 解释器。固定 Plan 字节 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，内含指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`。

Windows 新 clone 曾受全局 `core.autocrlf=true` 影响，Plan 工作树换行为 CRLF 而 Git blob 正确；本 clone 仅设置本地 `core.autocrlf=false` 并从自身 Git blob 恢复三个 J35 fixture 原字节，索引无差异。原始模型与旧证据仍在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\phase1…phase7`，只读复用。全部本轮模型、命令结果和大文件在被 Git 忽略的 `data/local/j35-contract-probes/`；`git check-ignore -v` 证实 `/data/local/` 生效。SIMLOX 每次调用前检查进程，未终止或占用用户 GUI。

复用隔离 Python 3.12.14 / SimPy 4.1.1。重新以 Rust 1.90.0 GNU、`--release --locked --offline` 从本 clone 构建，工具链与缓存均在旧用户工作区 `evidence/`，新构建输出只在本 clone `data/local/`。[构建脚本](../../scripts/simlox/rebuild_j35_rust.ps1)与本机 `data/local/j35-contract-probes/p0/rust-rebuild/result.json`、`cargo-build.log` 可核验；新 exe SHA-256 `eeaf9a437e3b12cc18402a0045dbe105008acdf975b2b29a2e310e1fe09c1ef4`，旧 exe `f02a0cfd9261aa7817191fbf1d4d5d17b7a2d0fbc40882b30b67dfc7184730a1`。两 exe 字节不同但同 Plan seed1 的完整 RunResult **逐字段相同**，见 `p0/rust-rebuild/old-new-rust-diff.json`。本次单样本运行不是性能测量。

固定 Plan seed1 的 Python 与新 Rust 都得到 `time=61464` 分钟、`natural_complete`、12713 条 trace、相同 Plan 指纹；`trace`、`metrics`、`terminal_state`、`seed`、`time`、`stop_reason` 完全相同。[精确比较脚本](../../scripts/simlox/compare_j35_run_results.py)仍发现 5 个 `sample_requests[*].value_minutes` 浮点末位差异，索引为 335、1315、1950、2000、3224，最大绝对差 `3.725290298461914e-09` 分钟，原始清单在 `p0/rust-rebuild/python-rust-diff.json`。因此「主要可观察输出相同」已验证，「完整 JSON 位级相同」不成立。

## 2. P1：取消判别矩阵生成，原生执行受阻

旧 `evidence/phase7/report.md` 所记的八 SID PM-only 20 波前 19 波对齐，第 20 波无随机故障：原生在 `176.967 h` 取消并中断第 8 步准备、释放资源，固定 Python/Rust 在 `179 h 20 min` 取消。它与 `STIM+DTIM−142 min` 计算一致，但只支持候选解释，不证明通用动态可行性算法。完整 PM-only 原生 88/104 起飞、Rust 89/104；这不是 RNG 差异。phase7 完整原始日志、首差、回导与哈希仍在旧证据目录。

[矩阵生成器](../../scripts/simlox/make_j35_cancel_matrix.py)从 phase6 已验证的两稳定 SID 模型（SHA-256 `ec93b454aceb58a6fb49f47fe1e16064ffb21a9e699c785fea39276c7e4c6b17`）派生 12 个隔离 JSON：全就绪；第二架在推定截止前/同刻/后就绪；共享人员/设备限额 1；零准备前/后；`DTIM=40 min`；`STIM` 前后平移 30 min；单准备步骤缩短 20 min；相邻后续波。每个 `data/local/j35-contract-probes/p1-*/provenance.json` 记录源、输入 SHA-256 和机器逐字段差分；所有变体保留两架需求、故障率零。它们用于区分准备是否开始/完成、资源竞争及 PM 同刻顺序；**未产生有效 SXI、回导、ENLOG 或结果，不构成规则证明**。

[原生运行脚本](../../scripts/simlox/run_j35_native_probe.ps1)逐步要求输出存在、回导 32 个非空业务表等价、转换 `Errors: 0`、SXO 大于 4 字节。实际对 `p1-before` 调 `-silent -jimport … -save … -log … -close` 返回 exit 0（`steps.json` 记录约 1.10 s），但 `.sxi` 缺失、`import.log` 为 0 字节，按脚本判无效。另用 [直接子进程预检](../../scripts/simlox/native_cli_preflight.py)对 phase7 **已经导入/运行验证**的 `sid8-pm-first20.sxi`（SHA-256 `749ad9aa0d0df57f9b5f0656621c655e0fca037093d40b0c5356a925e833fba6`）执行只读 `-jexport` 到新隔离路径，同样 exit 0、stdout/stderr 空、无回导、0 字节日志；原始结果为 `data/local/j35-contract-probes/preflight-direct/result.json`。程序 SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`，运行前无 Simlox 进程。该现象与本轮输入是否可转换无关；原因尚未定位，不能猜测为许可证或模型错误。旧 phase7 导入/回导的 32 个业务表另经新 [核对器](../../scripts/simlox/verify_native_roundtrip.py)重验全等，证明核对器能处理已有效证据，不证明本轮新模型有效。

矩阵仍欠第二架在同刻、准备全完成但等候、准备与释放同刻优先级、取消后已排队步骤和紧邻下一波的**原生事件**；所有格均标未验证。恢复 CLI 后须在每格检查 SXI/SXO、0 转换错误、非空表回导与 ENLOG 的 ready/分配/准备/取消/资源释放时刻，打印时刻换算小时→分钟并记录精度，不以总起飞数判断规则。

## 3. P2/P3：403 LRU 与可观察库存账

[逐件静态映射](j35-lru-static-mapping.csv)和 [汇总](j35-lru-static-summary.json)从固定 Plan、canonical 输入生成并先验哈希校验；403/403 个明确 LRU 有唯一源路径、组件/产品 ID、父链、每机安装槽、8 尾号、失效率/失效阈值、修理活动、人员/设备、时长、共享库存和运输路线。深度 2 为 167 个、深度 3 为 236 个；**没有直接挂系统根的 LRU**。每个产品有八个安装槽，合计推定 3224 个装机槽；这不是 3224 种库存品类。另有 20 个未标型中间件，均有正失效率。Plan 仅有两处共享库存池，基地初始 501 件、上级初始 0 件，单条容量 1、120 分钟运输路线；基层共享人员 40、设备 60，未按八 SID 复制。

固定 Python reference 中，失败组件引发 `replacement` 且该活动无静态备件时，按失败 **LRU 产品 ID** 注入数量 1 的备件需求；父链用于根部失效传播，修复完成重抽该组件寿命。Rust 对应路径已核查。该执行语义支持「失败的嵌套 LRU 自身是请求的产品」，但 canonical 父关系没有独立写明实际拆装边界、拆下坏件归属及维修回流，不能由嵌套结构断言父件仅聚合。SIMLOX UserDoc 印刷页 241/247 和字典区分系统一级 LRU/PRU/DU 与车间二级 SRU/SPRU/DP；把 403 LRU 转为二级件会改变领件和回流事务，phase6 的 PRU→SPRU 能力探针不证明无损。

本轮没有把 MTBF 常数冒充固定故障时刻，也没有新原生故障/库存试验。既有可执行 Python `b3-upstream-transport` 样本测试验证一次请求、一次运输、一次消费，初始现货 = 期末现货 + 消费量；这是**单端、可观察库存账**。完整 J35 的装机好/坏件、预留、在修、运输、报废、外流及维修回库并未全部作为同义原生/Rust 状态暴露，故实物守恒和需求守恒尚未验收。终点欠交不能算实物。需先获取上游逐产品物理换件决定与可信的共同故障注入，再测现货、零库存、两机争抢、回库再领、兄弟件和 PM/寿命交互。

## 4. 状态、门禁和复现

| 类别 | 实际结论 |
| --- | --- |
| Implemented | 来源锁定计划/manifest；十二格诊断 JSON 与逐字段差分；原生有效性严格检查；403 件静态映射；逐字段输出比较器、回导核对器、离线 GNU 重建脚本和行为测试；[独立合同提案](j35-common-contract-proposal.md) |
| Verified | 固定输入哈希；新 Rust 构建并与旧 exe seed1 全输出相同；Python/Rust seed1 仅 5 个采样浮点末位不同；403/403 LRU/共享池静态覆盖；旧 phase7 非空表回导全等；Python 最小运输单端库存账；本轮 CLI 失败事实 |
| Unverified | 十二格原生取消规则及通用算法；源物理换件边界；共同可控故障、CM/库存回流/物料与需求守恒；完整 104 波 PM-only、故障/资源/任务/停止及可比输出；独立 RNG 分布验收 |
| Blocked | 原生 CLI 对已知有效 SXI 亦无输出；phase7 第 20 波固定合同与原生取消时点不一致；403 LRU 不能无证据地重分类为二级件。三项阻断相互独立。 |

运行针对性测试：`python -m unittest discover -s tests/conformance -p test_j35_contract_probes.py -v`，本机 5/5 通过，其中旧原生回导及本地矩阵测试在非 4700-3 环境会明确跳过。可重跑顺序：先用 `scripts/simlox/rebuild_j35_rust.ps1`、`scripts/run_reference_plan.py` 和 Rust exe 跑固定 seed1；用比较器保存精确差异；用 `scripts/simlox/audit_j35_lru_contract.py` 重生映射；用 `scripts/simlox/make_j35_cancel_matrix.py` 生十二格；先跑 `native_cli_preflight.py`，仅预检成功后对各格用 `run_j35_native_probe.ps1`。生成器拒绝覆盖已有模型；新目录需隔离复制或全新工作树。本次本地 `data/local/` 保留所有原始输入、`provenance.json`、失败步骤/空日志与构建输出，不纳入 Git。

完整 PM-only 前 20 波已发生确定性事件分叉，且本轮原生新探针受阻；因此未预注册新候选分布、未复跑 1000 样本、未做同边界性能计时或给出加速比。旧候选 1000 样本只作历史诊断。恢复原生 CLI 并完成取消与换件两项独立规则判别后，仍须检验 104 波、共同窗口/终态和输出；只有通过这些门槛，再事先确定独立样本的指标、业务容限、方差/样本量与区间方法。未批准的容限或普通 `p>0.05` 不能证明等价。
