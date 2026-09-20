# O3 候选：故障状态稀疏数组

源码提交：`9400f0f21030cf7f5cec930df84f055109674c70`。对照 O1 提交：
`50857fef16977188956dabec0d9361ca0a8bb0aa`。两侧报告都记录源码束、可执行文件、Plan
文件与主机摘要，可直接比较。固定 Plan fingerprint 为
`7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。

## 语义验收

- 31 项 Python/Rust conformance 与 differential tests 通过；另有 Rust 定向测试覆盖稀疏适用性、
  两机状态隔离、`quantity > 1`、不适用组件仍抽样、missing timer 和终态业务键。
- Plan loader 新增稠密索引及组件/飞机等引用校验，异常计划显式失败。
- O1/O3 seed 0 full profile 的完整 `result_sha256` 均为
  `aa6e7ca01d2cb4044e1664a4ab27f476f0f4d1aefcefde93bdca1cc1f5d5f4d2`。
- 仍保持 61,920 分钟、19,275,687 个 component 扫描项和 459,832 次 Plan spec clone。

## 未插桩墙钟

每个表格单元为 6 次交错执行的中位数，括号为最小值–最大值。确认轮是独立的第二次进程调用。

| seed | 首轮 full | 首轮 summary | 确认轮 full | 确认轮 summary |
|---:|---:|---:|---:|---:|
| 0 | 0.243513s (0.238159–0.256429) | 0.232881s (0.228604–0.238214) | 0.244661s (0.239661–0.249093) | 0.234148s (0.232232–0.235445) |
| 1 | 0.209903s (0.208394–0.211035) | 0.202199s (0.199680–0.205539) | 0.210015s (0.209040–0.212353) | 0.201932s (0.199991–0.206424) |
| 7 | 0.175640s (0.174006–0.178116) | 0.164589s (0.162964–0.166596) | 0.174838s (0.172974–0.177736) | 0.163783s (0.162783–0.164624) |

相对固定的 O1 候选，首轮 full 三个 seed 分别提速 2.01×、2.16×、2.67×，确认轮为
1.96×、2.12×、2.63×；summary 两轮均呈现同方向收益。不同 seed 的故障暴露路径不同，因此不把
这些倍数外推到其他模型。

## 更新后的热路径

seed 0、5 次 full 插桩 profile 的执行中位数为 0.280495s，未插桩配对中位数为 0.238274s。
主要 phase 为：

| phase | 中位累计时间 | 插桩执行占比 |
|---|---:|---:|
| resource_dispatch | 102.838ms | 36.66% |
| failures | 32.801ms | 11.69% |
| preventive_generation | 18.494ms | 6.59% |
| preflight_generation | 16.951ms | 6.04% |
| operations_postflight_before_preparation | 14.608ms | 5.21% |
| job_progress_and_completions | 13.958ms | 4.98% |
| operations_postflight_after_dispatch | 13.618ms | 4.85% |

已插桩 Map reads 从 O1 的 39,584,579 降至 1,041,061，Map writes 从 19,271,774 降至 2；
这些是运行时显式标记访问，不是所有集合内部操作。failures phase 从 265.421ms 降至 32.801ms。

下一步执行 O2a：仅按飞机预计算 preventive cycle 列表并记录实际候选访问数。`matches_type`、
activity 预解析和通用 PreparedPlan 暂无隔离证据。resource dispatch 的活动集合优化归 O4，需在
O2a 后重新剖析。

静态 failure slot→component 列表目前仍按 Runtime 构建；执行墙钟从 Runtime 创建之后开始，
因此本报告不宣称初始化或批量内存收益。共享 prepared layout 必须单独测初始化、端到端和每样本内存。

## 文件

- `f35-observation-interleaved-seeds-0-1-7.json`：首轮交错墙钟。
- `f35-observation-confirmation-seeds-0-1-7.json`：第二轮候选复现。
- `f35-seed0-full-profile.json`、`f35-seed0-summary-profile.json`：插桩/未插桩配对及内部计数。
- `host-manifest.json`：环境与工具链。
