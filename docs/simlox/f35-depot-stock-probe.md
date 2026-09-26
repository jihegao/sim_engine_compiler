# F35 上级库存与备件调运探针

状态（2026-09-26）：**上级基地库存已补入独立的 canonical 和 SIMLOX 候选**，原始 fixture 与 [SIMLOX 工序候选 v4](f35-workflow-candidate.md)不变。canonical 参考运行观察到两次基地至基层的 120 分钟调运；SIMLOX 原生导入、回导和运行通过，但其现有聚合报告没有提供可核对的逐件发运证据。因此，SIMLOX 调运仍是**结构已建、执行语义未验收**，不能据此比较两引擎结果或效率。

## 唯一业务改动与来源

| 对象 | 固定身份与变体 |
| --- | --- |
| canonical 来源 | 上游 `spare_mvp` `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`；本仓库 `simulation-inputs.json` 字节 SHA-256 `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`。 |
| canonical 变体 | 只将 `support-org-dadui.inventory[product-f35-part-0018]` 从 0 改为 **2**；基层仍为 0。变体 SHA-256 `b78559aae597685a67a673bb75c78fbedbbacea23648e4c99a9ba4d4ec3b596d`；编译 Plan 指纹 `553fb1736716912a7e253e7d44fdd92421e562c1c0494331ffcda6f181c05a57`。其余字段逐项相同。 |
| 路线 | 原 Plan `logistics-8-transport-0` 已规定基地 `support-org-dadui` → 基层 `support-org-1783479792728`，`transport_minutes=120`、`capacity=1`；本探针未改路线。参考运行中 `capacity` 是**单次发运最大件数**，不是同时在途车辆数。 |
| SIMLOX 来源 | v4 候选 JSON `e32bb75b94b44573d208fe415243c223de88802f1e3df99c8bd2ab47ff772e6a`，原生回导模板 `a73c6295d5e93bf93d84d610ce89edfcde9d7d15c60c6c482a6756650055611f`；生成脚本：[build_f35_depot_stock_probe.py](../../scripts/simlox/build_f35_depot_stock_probe.py)。 |
| SIMLOX 变体 | `product-f35-part-0018` 映射 `Item.IID=F35-PART-2602030200000801`。`StockAllocation` 新增 BASE 0 件、DEPOT 2 件；`StationStructure` 新增 `BASE→DEPOT` 上级关系，`TFRMS=2` 小时、`OPOL=FAST`。SIMLOX 要求填写反向 `TTOMS`，暂填 **2 小时假设**；其路线表不等价表达 canonical 的单次发运件数上限。JSON SHA-256 `336b2247a770f92427a46a6bc223fbc46a0578f6fada05ed1149d4bde0d40ff3`。 |

补 2 件的理由是原始种子 1 oracle 有两次 `product-f35-part-0018` 缺件请求；这是一项明确的试验输入修改，不是声称上游原模型本来有这些库存。SIMLOX 2017 安装手册 `UserDoc/SIMLOX.pdf` 第 210、219–220、327–329 页描述了修复件的库存循环、需求沿上级站点传播和 `StationStructure.TFRMS/TTOMS`。对可修复件填写 `StockAllocation.ROSIZ` 会被 SIMLOX 警告 #170 忽略，因此最终候选未填写该字段。

## 可核对的运行结果

| 核对 | 结果 | 解释范围 |
| --- | --- | --- |
| canonical 参考运行，种子 1 | 3 次该产品需求；866 分和 927 分各从基地发运 1 件，分别于 986 分和 1047 分到基层；`transport_replenishment_events=2`、`total_transport_delay_minutes=240`、`spare_consumed_total=2`。49626 分另有 1 次缺件。 | 证明新增上级库存被 canonical 参考运行调用。两个发运时间重叠，符合其按**单次件数**使用 `capacity=1` 的实现；不证明 SIMLOX 同样调度。 |
| SIMLOX 原生回导 | `StationStructure` 1 条有效关系；`StockAllocation` 从 167 增至 169 条，新两条的站点、件号、`STSIZ=0/2` 均逐字段保留；输入转换 0 错误、0 警告、0 提示。 | 证明候选存入原生模型并能运行。原生 `.sxi` SHA-256 `a1536ff5223f48700c013b92e66335ae5c12f8a25663ee70763a52a617b5a3aa`；回导 JSON `a9e788ce8befc625da98ccc7de5a4424869373788b7ad9455ced405449aa0ce8`。 |
| SIMLOX 单次运行 | 结果报告为 1 次重复、0–1032 小时；原始 `-jsonreport` SHA-256 `db8600eb0c99f5f615a46908b80e4395fcb7356ba272495b1090d2b2335f1037`，与未补库 v4 的原始报告**逐字节相同**。 | 未观察到补库对该次 SIMLOX 汇总结果的影响；不能把 canonical 的两次调运移植为 SIMLOX 结果。 |
| SIMLOX 100 次重复诊断 | 只把两边 `Control.NREPS` 改为 100，其他各自不变；未补库与补库的原始报告 SHA-256 均为 `62228505c31f11d5c67fbec855fdcbd2bca95ff236b3979cf42f3832e978e8ac`。另将目标及两级母件 `Item.TRACK=Y`，`-jsonreport` 仍未导出逐件表。 | 100 次重复和追踪开关只是定位证据缺口，不是效率基准；现有输出无法判定目标件是否被请求、是否经即时整修满足、或有无逐件在途记录。 |

4700-3 原始证据在 `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-depot2-v2\`；100 次重复诊断分别在 `simlox-f35-baseline-100`、`simlox-f35-depot2-100` 和 `simlox-f35-track-100` 目录。本工作树 Git 忽略的镜像在 `data/local/simlox-f35-transport-probe/`，包含 canonical 输入变体和摘要、SIMLOX JSON、`.sxi`、`.sxo`、原生回导、未经改写的结果及日志。中间的 v1 候选留在该镜像中，供追查 #170 警告；最终使用 v2。

[verify_f35_depot_stock_probe.py](../../scripts/simlox/verify_f35_depot_stock_probe.py) 对唯一 canonical 库存改动、参考调运时间、SIMLOX 原生站点/库存回导、日志中的输入输出关联，以及单次和 100 次报告的上述“未观察到变化”结论逐项复核；本机 `verification.json` 的状态为 `upper-stock-native-roundtrip-verified; SIMLOX transport-not-observed`。

SIMLOX v4 的 `ItemRepair.DIRPT=0` 仍是拆下件即时整修占位，维修/库存事务尚未与 canonical 配对。下一步若要声称**真实调运已对齐**，需在 SIMLOX 中取得目标件需求、发运和到货的逐件证据，或建立能强制触发该需求的独立小模型，再核对时间、数量、等待与结果口径；目前的补库探针不满足这一验收条件。
