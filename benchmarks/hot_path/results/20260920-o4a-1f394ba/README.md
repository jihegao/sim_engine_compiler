# O4a 候选：waiting/running 作业活动集合

源码提交：`1f394ba5303d3ddd0f47c30935cf1b241c649e15`。固定对照为 O3 提交
`9400f0f21030cf7f5cec930df84f055109674c70`。两侧 release 二进制分别记录源码束、
可执行文件、Plan 文件与主机摘要。固定 Plan fingerprint 为
`7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。

## 实现与语义验收

- Runtime 维护按 job index 排序的 waiting/running 集合；历史作业仍保留在结果中，但
  `resource_dispatch` 与 `job_progress_and_completions` 只访问活动候选。
- 创建、空 activity、启动、步骤完成、作业完成与取消均通过同一状态转移函数维护集合；debug
  构建会从全部 jobs 重建集合并断言一致。
- waiting 仍按 `(activity.priority, started_time.unwrap_or(current_minute), job_id)` 排序；
  定向测试用与创建顺序相反的 job ID 验证第三排序键。running 仍按原 job index 顺序推进。
- 同分钟步骤完成后可重新分派，新建 job 可同分钟启动；零时长步骤仍到下一分钟 progress 才完成。
  取消立即释放人员/设备，但备件预约仍到下一分钟 `transport_arrivals` 归还。
- Rust fmt/check/clippy、15 项 Rust 测试，以及重建 PyO3 binding 后的 31 项 Python/Rust
  conformance 与 differential tests 均通过。F35 seeds `0、1、7` 的 full/summary、截断
  horizon 和 `[7,0,7,1]` 的 1/3 线程批量路径均在覆盖内。
- O3/O4a 的 RNG、完整 trace、metrics、终态、时间、停止原因及身份在全部配对报告中精确一致。
  seed 0 full 的 `result_sha256` 继续为
  `aa6e7ca01d2cb4044e1664a4ab27f476f0f4d1aefcefde93bdca1cc1f5d5f4d2`。

## 候选独立复测

每个单元为 6 次执行的“中位数 / 均值 / 最小值–最大值”。这两轮只运行 O4a 固定二进制，
用于候选复现；收录判断以下一节的同会话 O3/O4a 对照为主。

| seed | 首轮 full | 首轮 summary | 确认轮 full | 确认轮 summary |
|---:|---:|---:|---:|---:|
| 0 | 0.244302 / 0.243397 / 0.235659–0.249668s | 0.230826 / 0.231583 / 0.228054–0.236182s | 0.234997 / 0.235627 / 0.234065–0.237904s | 0.225734 / 0.225769 / 0.224164–0.227079s |
| 1 | 0.206902 / 0.208025 / 0.203044–0.214893s | 0.197302 / 0.199567 / 0.195271–0.212034s | 0.202991 / 0.203153 / 0.201931–0.205039s | 0.195871 / 0.195683 / 0.193986–0.197794s |
| 7 | 0.166787 / 0.167767 / 0.165479–0.172424s | 0.155786 / 0.156396 / 0.154850–0.158916s | 0.165508 / 0.166247 / 0.164454–0.170250s | 0.156014 / 0.155933 / 0.155319–0.156416s |

## 同会话固定二进制对照

为分辨低于旧报告波动的差异，重新从 O3 和 O4a 提交构建两个独立 release 二进制，做四组
同会话对照，并在 A/C 与 B/D 之间反转二进制先后顺序。下表是 O4a 相对 O3 的中位执行时间
改善，正值表示 O4a 更快。

| 会话 | seed 0 full | seed 0 summary | seed 1 full | seed 1 summary | seed 7 full | seed 7 summary | 六单元中位 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5.06% | 5.36% | 5.01% | 4.96% | 7.18% | 8.54% | 5.21% |
| B | 4.84% | 5.35% | 1.29% | 1.02% | -0.95% | 1.24% | 1.26% |
| C | 8.13% | 6.26% | 5.52% | 5.44% | 7.18% | 7.54% | 6.72% |
| D | 6.47% | 6.01% | 5.88% | 6.47% | 5.73% | 5.97% | 5.99% |
| 跨会话中位 | 5.77% | 5.69% | 5.27% | 5.20% | 6.45% | 6.76% | — |

24 个会话单元中 23 个正向，18 个达到 5%。B 会话较弱，并含 seed 7 full 的 0.95% 回退；
因此不声称每轮、每个单元都超过 5%。A/C/D 独立复现，且每个 seed/观测组合的跨会话中位
均超过计划中的约 5% 工程筛选线，O4a 据此收录。

## 更新后的热路径

seed 0、5 次 full profile 的未插桩配对中位数为 0.234443s，插桩分钟循环中位数为
0.280736s。主要 phase 为：

| phase | O3 中位 | O4a 中位 | O4a 插桩占比 |
|---|---:|---:|---:|
| resource_dispatch | 102.838ms | 102.484ms | 36.51% |
| failures | 32.801ms | 33.374ms | 11.89% |
| preventive_generation | 18.494ms | 21.110ms | 7.52% |
| preflight_generation | 16.951ms | 17.588ms | 6.27% |
| operations_postflight_before_preparation | 14.608ms | 14.745ms | 5.25% |
| operations_postflight_after_dispatch | 13.618ms | 13.669ms | 4.87% |
| job_progress_and_completions | 13.958ms | 8.836ms | 3.15% |

summary 的 job progress 从 O3 的 10.571ms 降至 5.214ms；full/summary 分别减少约
36.7%/50.7%。resource dispatch 只从 102.838/100.752ms 变为 102.484/98.376ms，
只是小幅趋势，仍是首要热点。插桩总分钟循环 full 基本持平，summary 约改善 0.95%；
不能用单 phase 降幅代替正式未插桩结论。

O4a seed 0 的 waiting/running 实际候选访问为 150,975/90,839，峰值集合为 7/8。
旧 `job_scan_items=49,410,043` 继续保留为历史可比暴露口径，但还包含 transport、preventive
等未优化扫描，不能用两者相除宣称总 job 扫描减少比例。

## 范围与下一步

本轮只优化 waiting/running 候选。按 mission 的 active preflight、按 aircraft 的 preventive、
取消预约、shipment/job lookup 与 mission 时间集合仍未实现。下一切片只评估 active preflight
索引；F35 没有 shipment/预约返还负载，因此不拿该案例为运输索引背书。完整端到端、初始化和
每样本内存也未测量，本报告不宣称这些边界上的收益。

## 文件

- `f35-observation-interleaved-seeds-0-1-7.json`、`f35-observation-confirmation-seeds-0-1-7.json`：O4a 两轮独立复测。
- `paired-{a,b,c,d}-{o3,o4a}.json`：四组同会话固定二进制对照原始记录。
- `f35-seed0-full-profile.json`、`f35-seed0-summary-profile.json`：插桩/未插桩配对及内部计数。
- `host-manifest.json`：O4a 环境与工具链。
