# O1 候选：移除逐分钟任务定义深拷贝

源码提交：`50857fef16977188956dabec0d9361ca0a8bb0aa`。固定 Plan fingerprint：
`7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。
环境、编译器与主机信息见 `host-manifest.json`；两份 v2 交错报告及两个 profile 均记录了
源码束、可执行文件和 Plan 文件摘要。

## 语义验收

- 31 项 Python/Rust conformance 与 differential tests 通过。
- F35 seeds `0、1、7` 的 full 完整结果与独立 Python reference 一致；summary 的 RNG、
  metrics、终态、时间、停止原因和身份均与 full 相同，trace 为空。
- 重复 seeds `[7,0,7,1]` 在 1/3 线程、full/summary 和截断 horizon 下保持输入顺序与逐样本等价。
- O1 保持 61,920 分钟和 19,319,040 个 mission 扫描项；`plan_spec_clones` 从旧 profile
  的 19,778,872 降至 459,832，减少值恰好为 19,319,040。

## 未插桩墙钟

每个表格单元为 6 次交错执行的中位数，括号为最小值–最大值。确认轮是独立的第二次进程调用。

| seed | 首轮 full | 首轮 summary | 确认轮 full | 确认轮 summary |
|---:|---:|---:|---:|---:|
| 0 | 0.488579s (0.480546–0.498004) | 0.470935s (0.466637–0.484549) | 0.478468s (0.476286–0.482033) | 0.468493s (0.463349–0.615782) |
| 1 | 0.452403s (0.446430–0.466335) | 0.439836s (0.436631–0.448981) | 0.444814s (0.439833–0.446294) | 0.435144s (0.433050–0.442416) |
| 7 | 0.469650s (0.466522–0.699738) | 0.462285s (0.454366–0.515164) | 0.460424s (0.456113–0.469284) | 0.449987s (0.448887–0.456646) |

与旧 seed 0 报告相比，首轮 full 中位数由 2.629474s 降到 0.488579s（5.38×），summary
由 2.605351s 降到 0.470935s（5.53×）。旧报告没有源码束和可执行文件身份，因此这只能说明
与已保存基线的强趋势，不能当作两个已固定二进制的严格 A/B。候选自身的第二轮复现支持收益稳定存在。

summary 在首轮三个 seed 的配对中位比值为 full 的 0.971–0.974；它仍将 seed 0 结果从
4,212,927 bytes 降至 1,392,096 bytes。个别运行存在系统噪声离群值，正式结论使用中位数并保存全部记录。

## 更新后的热路径

seed 0、5 次 full 插桩 profile 的执行中位数为 0.517418s，未插桩配对中位数为 0.480660s。
主要 phase 已变为：

| phase | 中位累计时间 | 插桩执行占比 |
|---|---:|---:|
| failures | 265.421ms | 51.30% |
| resource_dispatch | 106.748ms | 20.63% |
| preventive_generation | 19.073ms | 3.69% |
| preflight_generation | 16.736ms | 3.23% |
| operations_postflight_before_preparation | 14.670ms | 2.84% |
| job_progress_and_completions | 14.020ms | 2.71% |
| operations_postflight_after_dispatch | 13.751ms | 2.66% |

旧报告中的三个 mission phase 不再主导运行时间。下一步优先执行 O3 故障状态数组化；O2 的静态
关系预计算只在相应调用点仍有可测成本时推进，resource dispatch 的活动集优化归 O4 单独验收。

## 文件

- `f35-observation-interleaved-seeds-0-1-7.json`：首轮交错墙钟。
- `f35-observation-confirmation-seeds-0-1-7.json`：第二轮候选复现。
- `f35-seed0-full-profile.json`、`f35-seed0-summary-profile.json`：插桩/未插桩配对及内部计数。
- `host-manifest.json`：环境与工具链。
