# J35 起飞前保障资源竞争探针

状态（2026-09-26）：**SIMLOX 2017 原生运行已证实起飞前工序的有限专业人员会形成资源等待，并显著改变固定任务的开始数；20 分钟延迟窗可配置。** 这是 SIMLOX 内部受控扰动，不是与 `spare_mvp` 的逐任务语义等价证明。逐项指纹、模型差异和结果算术见[机器可读核对结果](j35-preparation-resource-probe.json)，核对程序为 [verify_j35_preparation_resource_probe.py](../../scripts/simlox/verify_j35_preparation_resource_probe.py)。原始模型、回导和结果保留在 4700-3 的 `C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-page`、`simlox-j35-p-arm1-probe`、`simlox-j35-p-arm1-dtim20-probe` 三个目录，本机镜像存于忽略目录 `data/local/simlox-amd128-page/`。

三组模型都是 8 架飞机、43 天、104 波固定任务。`MISSION_PREP` 包含 14 道串行起飞前工序，合计 142 分钟，任务前通知 `NOPER=3h`。军械人员 `P_ARM` 只出现在其中 8 道 `SubTaskResource` 需求，不参与 PM/CM `TaskResource`。第一组与第二组的业务字段只改 `ResourceAllocation.P_ARM.RQTY=10→1`，另改一处说明文字；第二组与第三组只改 104 行 `OperationProfile.DTIM=20/60h→NULL`。这里 `NULL` 采用 SIMLOX 默认 **0 小时**的最迟开始窗口。三个模型均通过原生导入、回导、运行和报告导出，回导的 31 张模型表 `instances` 逐行相同，输入转换为 0 错误、0 警告。

| SIMLOX 运行 | 军械人员容量 | 最迟开始窗口 | `NRW>0` 的半小时区间 | 固定任务开始数 | 成功数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| J35 候选 | 10 | 20 分钟 | 0 / 2064 | 92 / 104 | 79 / 104 |
| 资源受限 | 1 | 20 分钟 | 310 / 2064 | 26 / 104 | 25 / 104 |
| 资源受限、零延迟窗 | 1 | 0 分钟 | 312 / 2064 | 12 / 104 | 12 / 104 |

`ResourceResults.NRW` 是区间内未满足资源需求的平均队列。容量从 10 降到 1 后，队列从全零变为 310 个非零区间，同一 20 分钟窗口下开始任务由 92 降为 26；这证实模型会因起飞前资源不足而等待，并影响任务能否开始。在容量 1 不变时，将窗口从 0 增到 20 分钟，开始任务由 12 增到 26，说明延迟开始窗口会容纳一部分准备较晚的任务。`NRW` 是聚合队列，不能反推每波准确晚起飞分钟数，也不能将所有未开始任务单独归因于这一个资源；后续故障、库存和随机轨迹会随任务变化。

SIMLOX 原机手册 `C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf` 印刷页 273、275 定义 `OperationProfile.DTIM` 为固定任务允许的最大延迟，默认 0；页 294–296 说明 `MissionPreparation` 可挂任务及资源工序，并在通知期内执行；页 397–399 定义子工序资源数量；页 750、755 定义 `NRW`。文档和软件指纹见[来源记录](source-provenance.md)。

对 `spare_mvp` 的进一步验收仍需 SIMLOX 逐波准备开始、资源申请、等待、实际起飞或取消事件；当前 `-jsonreport` 只有聚合分数和半小时队列。模型里还同时叠加 Plan 通用人员/设备和页面专业资源，不能把这组三组 SIMLOX 数字直接解释成 `spare_mvp` J35 的效率或成功率。
