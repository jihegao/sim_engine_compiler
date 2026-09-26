# J35 / SIMLOX 与 Rust：4700-3 的 1000 样本诊断

状态（2026-09-26）：**双方已各运行 1000 个独立样本；当前模型的波次成功率与起飞率明显不同，不能判为等价模型，也不能计算等价加速比。** 本文件记录可比较的聚合指标及限制。原始 phase2/phase3 报告、脚本、模型、原生日志和批量输出在 4700-3 的 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\`。本工作树的 Git 忽略目录 `data/local/simlox-4700-3-event-parity/` 保存报告、原生汇总和分析副本，保留原始字节 SHA-256。

## 输入与阶段二修正

固定 J35 Plan 来自 AMD128 主仓库 `spare_mvp` 修订 `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`，经既有 ProjectJsonExporter → SimulationAdapter → 本仓库编译而成；文件 SHA-256 `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb`，指纹 `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`。SIMLOX 2017 程序 SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`；Rust GNU release SHA-256 `f02a0cfd9261aa7817191fbf1d4d5d17b7a2d0fbc40882b30b67dfc7184730a1`。

阶段二在隔离原生副本中加入 `SystemDeployment.PLID`、8 组 `PrelifeData` 与 `PrelifeDataAge`，并为 `PM_25H` 加入 `CALHOURS=168` 的第二计数器。手册确认两计数器先到者触发同一 PM 并复位；原生导入、回导与运行成功。第 24 小时三架飞机的 PM 触发与 Rust 相同。另移除原候选起飞前 27 条及两个 PM 工序额外的专业资源需求，使此探针只占固定 Plan 的通用 `PERSONNEL×1`、`DEVICE×1`。阶段二的 PM 通用资源模型 JSON SHA-256 为 `cfd738d94cde00df4537442e8c57112dfe5486fd107f88f940fff29e20d426e5`，原生 `.sxi` 为 `5db5f97ba957819adc4e354e641b04214d19e2f32f20fc76880ce813c82d6f9c`。

逐事件探针还找到第 56 小时同波次的候选用机序位分歧，以及其后的 PM、故障、CM、库存和停止边界差异。`PLIND` 到原生运行实例及固定尾号的连接尚未核实。SIMLOX 使用 Lehmer 流，固定 Rust/Python 使用 MT19937；同一个整数 seed 不能要求同一随机轨迹。单故障探针只证明 SIMLOX 对同字节输入可重复，尚未取得共享外生故障时刻接口。详见原机 `evidence\phase2\report.md`，原始报告 SHA-256 `ec574dd5a38fa2f463c3c5cb541478cbb959e828349c173c298bf56c6bc56d8a`。

## 104 波的共同观察指标

两个引擎均输入 8 架、43 天、104 个计划波次、每波需 2 架、成功点 0.75。SIMLOX `ResultSummary.MSUF/MSTF` 分别是成功/已开始的固定任务波次除以计划 104 波；Rust 分别用 `successful_mission_waves/104` 和终态中 `actual_start` 非空波数/104。Rust 1000 样本全部有 104 个已决波次，起飞、取消和成功数已与终态双向核对。SIMLOX 固定报告到 61920 分钟；Rust 有 195/1000 个样本在 61464–61920 分钟间自然完成，故只使用此前已决的波次指标，不比较时间平均可用性或期末库存。

原生批量模型仅从上述阶段二副本改变 `Control.NREPS:1→1000`、`ENLOG:Y→N`，回导 35 张表逐行一致，转换 0 错误/0 警告。模型 JSON SHA-256 `d37f509d062bba1883fd5d781f1fdc9338db66e5af899a64539675f1ab9c118a`，`.sxi` `8eba9b1596cada2fd83d6f6b0d0b049c12a371acdf8fcd46203bc6231360c25f`，`.sxo` `7d4a58b4556a27d3afb6d3b8e00c3c85844745764cd261bb50ad9acacef6a273`，原始报告 `abc49c90ce07452d893713ccfbff658080102d08e430dc15316d3300dfeda88a`。原生报告只含 1000 次的聚合均值和相对标准误；手册中的逐 repetition 结果需报告设置 “Replication results” 与 CLI `.sxs` 配置，当前没有可核对配置。Rust 使用固定 Plan、seed 1…1000、10 批各 100、单 worker、`summary` 观测，保留逐样本 metrics 与终态。

| 104 波中的比例 | SIMLOX 均值 | Rust 均值（逐样本 SD） | SIMLOX − Rust 的描述性 95% 均值差区间 |
| --- | ---: | ---: | ---: |
| 成功 | 0.754260 | 0.697260（0.075615） | **+0.057000**，[+0.052015,+0.061985] |
| 起飞 | 0.844913 | 0.781260（0.072542） | **+0.063654**，[+0.059084,+0.068224] |
| 取消：1 − 起飞 | 0.155087 | 0.218740 | **−0.063654**，[−0.068224,−0.059084] |

区间以原生 `均值×相对标准误`、Rust 样本 SD/√1000 和独立样本正态近似计算；没有将不同 RNG 的 seed 配对。Rust 成功波数每样本 5%/中位/95% 分位数为 59/73/83，原生默认报告缺逐样本分位数。汇总成功率除以汇总起飞率，SIMLOX 为 0.892706、Rust 为 0.892481；这是定位起飞前差异的线索，**不是**逐样本条件成功率。主指标已相差约 5.9 个成功波及 6.6 个起飞波/样本，差值区间远离零。业务容限尚待确定；即使按每样本不到一波（`1/104`）的建议容限，也明显不能判等价。

故障、PM、修复、库存调运、资源等待和可用性仍缺同定义的原生逐样本字段，不能用 `SystemResults.NFAIL/NPMT`、`StockTotalResults.NBO` 或 `ResourceResults.NRW` 直接替换 Rust 事件数。原生 30 分钟区间状态与 Rust 任务/事务计数的单位也不同。完整分析数据及逐样本 CSV 保存在原机 `evidence\phase3\distribution-analysis.json`、`rust-samples.csv`，原始 phase3 报告 SHA-256 `da8e90d3c96f1a04ab7bae0b142b43411f99ee1edc720727770d974f9c01f4dc`。

## 原始时间和解释范围

同机 Windows 10 Pro 19045、Ryzen 7 4700U、单线程：SIMLOX 1000 repetitions 的内部仿真为 **24.50 秒**，转换 0.03 秒、保存 0.12 秒、CLI 运行步骤外部墙钟 26.2285 秒；模型导入和报告导出另为 1.0534 与 2.0404 秒。Rust 10×100 `summary` 批次的外部墙钟合计 **384.062 秒**，包括 10 次进程启动、加载、初始化、执行、JSON 序列化及约 2.027 GB 写盘。SIMLOX 是一个进程并输出约 4.9 MB 的原生结果，保存边界不同；没有三轮同边界分段计时，也没有通过模型等价验收，**这些时间不可相除成等价加速比**。

下一步是用无故障、无 PM 的受控诊断以及逐项加回机制，定位起飞率差异；只在业务指标与结构口径闭合后重跑修正版 1000 样本，并进行同等观测负载下的重复分段计时。
