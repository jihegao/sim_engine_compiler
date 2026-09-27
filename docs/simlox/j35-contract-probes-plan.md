# J35 合同判别探针计划（4700-3）

状态：原生运行已由协调端 SSH 上下文恢复；取消首版十二格、临界 PM 修正版八格与一件共享备件第三版六格均有效。首版 P2 六格因 `RSEED` 数字回导字符串不全等停止，第二版因原生转换错误 `#2050` 与 4 字节 SXO 判无效；失败证据保留。第三版 `p2c-*` 恢复已验证源模型的 FRT 层级，逐事件证明共享现货争抢、欠交、修理回流与再领，但未证明与固定 403 LRU 的物理交易等价。结论见 [报告](j35-contract-probes-report.md)。目标是在保留固定 Python/J35 Plan 合同的前提下，判别 SIMLOX 2017 的取消、换件和库存机制；每项结果标为已验证、未验证或受阻。局部切片通过不升级为完整 J35 等价。

## 固定来源与前置条件

| 对象 | 固定身份 |
| --- | --- |
| Git 来源 | bundle 克隆 `codex/simlox-semantic-alignment`，提交 `526820f4631ceeb7c732f24b8a1c3e0cabcbea97`，祖先 `e9b6391fffd918e0f6e742bd1ef0e1312921b769`；工作分支 `codex/simlox-j35-contract-probes` |
| AMD128 上游 | `spare_mvp` 修订 `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`；ProjectJsonExporter → SimulationAdapter → `integrations/spare_mvp`，不解释 Project JSON |
| J35 Plan | `tests/fixtures/spare_mvp/j35-amd128-0e709bd/execution-plan.json`，字节 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，Plan 指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f` |
| 原生程序与证据 | SIMLOX 2017 `Simlox.exe` SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；旧 `evidence/phase1…phase7` 只读；新运行仅存被忽略的 `data/local/j35-contract-probes/` |

Windows Git 全局 `core.autocrlf=true` 曾使新克隆的 Plan 工作树字节 SHA 成为 `311ae763…`。Git blob 和旧只读证据均为固定 `44cfed…`；此 clone 的本地 `core.autocrlf=false`，仅把三个 J35 fixture 从原 Git blob 恢复 LF，索引无差异、工作树干净。所有脚本先复核固定字节。

运行前检查 SIMLOX 进程；不终止别人的 GUI。原生探针均要求 `-jimport/-jexport/-calc` exit 0、`Input conversion completed. Errors: 0`、有效非空 SXO、非空业务行回导核对，并保留 ENLOG、命令、SHA 与首差。ENLOG 只用于首重复事件，不作吞吐负载。原生时间为小时文本且打印精度有限；Rust/Python 为分钟。不同 RNG 种子编号不配对。

## 工作包、验收与停止条件

| 包 | 要执行的判别 | 验收与停止条件 | 状态 |
| --- | --- | --- | --- |
| P0 来源与环境 | 确认 bundle HEAD/祖先、LF Plan 指纹、原生/运行器版本、Python/Rust seed1 范围；写来源 manifest 与独立提交 | 精确记录 `sample_requests` 浮点末位等剩余差异；若 Plan/程序指纹改变则停止依赖它的探针 | 已验证：离线 GNU release 重建、固定 Plan seed1；5 个浮点差异 |
| P1 取消规则矩阵 | 从 phase7 八 SID、PM-only 前 20 波反例及更小两机模型复制隔离变体；第二架在候选截止前/同刻/后可用；未启动/部分/全完成准备；共享资源竞争对照；变 STIM、DTIM、单步时长；PM/资源释放/取消同刻；取消后排队作业与后续波 | 对每格核对输入差分、原生日志的通知/分配/准备/等待截止/取消/释放、Rust/Python trace；区分已测规则与 `STIM+DTIM−准备时长` 假说。若小探针已反证固定合同，记录最小反例并停止“等价”判定，不改固定 Plan | 协调端首版 12 格与修正 8 格全部有效；证明缺机提前超时、选齐后资源拖延至末窗、PM 临界前/同打印时刻/后回归、DTIM/步骤时长/零准备移动等待截止；内部同刻精度与完整104波仍未验收 |
| P2 换件事务 | 先检查 canonical 的装机实例、产品库存和父层级语义，再做可控单故障：有库存、零库存、两机争同件、回库再领、兄弟件、PM/寿命和终点在修；比较系统直接更换与 PRU→SPRU 资格 | 故障时刻必须显式注入或有已验证确定性触发；逐件记录装机/现货/预留/待修/在修/运输/报废、需求满足/取消/未满足。无法使源端同故障时，停止跨引擎事件等价，保留单端能力证据 | 已检查 Plan/Python 直接请求失败 LRU 产品；`p2c-*` 六格有效原生日志验证首两故障和共享一件现货、欠交、二级修理回流与再领，重复输入事件一致。故障是已观察的原生固定 seed 首样本，不是同 Rust 的显式 tape；兄弟件/PM 交互、全物理守恒和跨引擎事件等价未验收 |
| P3 403 LRU 全覆盖 | 对 canonical/Plan 的 403 个 LRU、20 中间件、八 SID 生成静态映射和行为分类；区别产品品类、安装槽、实例和库存池 | 每项有来源路径、父边界、数量、资源、活动、时长、失效作用、年龄计数；对共享库存/资源给唯一池验证。无上游直接换件证据的二级重分类标未验收 | 已验证 403/403 静态覆盖与共享池；源物理换件边界及装机件物料守恒未验证 |
| P4 共同合同提案 | 仅当固定合同与原生机制冲突时写独立版本化提案，不改现有 Python、Rust、固定 Plan | 同时列出取消和 LRU 两项独立阻断；局部通过的子集单独命名 | 已写待批准的独立版本提案，现有合同未变 |
| P5 分布与性能门槛 | 完整 104 波 PM-only、确定性故障/CM/库存/资源、终态与输出口径通过后，预注册指标、容限、方差/样本量，再考虑双方各 1000；语义与分布都通过才做同边界三轮计时 | 未过即不重跑大批量、不算加速比；任何新计时限定为实际工作流边界 | 门禁关闭；没有新 1000 样本或加速比 |

## 提交与交付

至少三个独立提交：①来源/计划；②可重跑探针、非专有最小夹具与行为测试；③审计与验收报告。运行原件只在 `data/local/`，Git 中仅收脚本、最小可公开夹具、差分摘要和文档。完成后尝试推送并针对 `main` 开 PR；若 DNS/凭据不可用，交付完整历史 `delivery.bundle`、`delivery.json`、`pr-body.md`、`final-report.md`，不输出凭据。
