# SIMLOX 可行性阶段效率对照

本文记录在 `4700-3` 上运行 SIMLOX 2017 示例案例的方法和现有证据，供可行性阶段估计商用仿真软件在这些完整场景上的运行量级。

这是一项外部工具效率参照。SIMLOX 示例不是本项目通过 `integrations/spare_mvp` 导入的 canonical `simulation_inputs`，目前也没有把这些模型映射为同语义的 Execution Plan。因此这些数据不构成本项目的语义等价验收、Rust 性能结论或跨引擎加速比。

## 机器与输入

2026-09-24 的测速记录注明：SIMLOX 2017，AMD Ryzen 7 4700U，8 核/8 逻辑处理器，可用物理内存约 7.42 GiB；每次运行使用 8 线程。运行机器为 Windows 主机 `4700-3`（SSH 地址 `100.96.129.117`）。重新测量时应重新记录软件版本、CPU、逻辑处理器数、内存、供电/负载状态和运行日期。

| 内容 | `4700-3` 上的路径 |
|---|---|
| SIMLOX 安装的原始 Demo `.sxi` 案例 | `C:\Users\Public\Documents\Systecon\SIMLOX\Demo` |
| 原始工作目录、案例的 `.1000.sxi` 输入副本和运行脚本 | `C:\Users\user\Documents\Codex\2026-09-24\w\work\benchmark` |
| 2026-09-24 首轮汇总、日志和结果 | `C:\Users\user\Documents\Codex\2026-09-24\w\outputs\simlox-benchmark` |
| 2026-09-25 独立复跑的输入副本、12 份运行日志、12 个 `.sxo` 和 `timings.json` | `C:\Users\user\Documents\Codex\2026-09-24\w\outputs\simlox-rerun-20260925` |
| SIMLOX 命令行程序 | `C:\Program Files\Systecon\SIMLOX\Simlox.exe` |

首轮记录说明：输入由官方 `-jexport` / `-jimport` 转换，仅把 `Control.NREPS` 改为 `1000`；随机种子、仿真时长、资源分配点和结果收集设置沿用原示例。每个运行都使用工作目录副本。首轮目录的 `run.ps1` 还包含失败的教程案例；只复跑下文列出的四个成功案例，不要直接运行包含五个案例的脚本。

用于复跑的四个输入 SHA-256：

| 案例 | 输入 SHA-256 |
|---|---|
| `aircraftorg` | `2FB830592D0764387F3CA6B54B5BEBFDE7E320B364C24DD1AFC5925271C24FFA` |
| `Torpedo Case` | `B4FE06D3C2130914727425008E5E6DB212F6F7641A9DEE8C733263F4B837CFF3` |
| `wbend` | `26F9872F4FF3C580B1FBAEEF0A7618E4022617CDDAFCFC47A35DFD2B5FB68A40` |
| `wbT2fix` | `6171189B631AD1A75CC5161209FB1BD8300A1670FCB0C7F36123722F95142E74` |

复跑时先核对这些输入指纹；输入、日志和 `.sxo` 结果放入新的独立目录，避免覆盖已保存证据。

## 运行方法

对每个案例用同一份 `*.1000.sxi` 输入运行三次，线程数固定为 8。将输入复制到本轮独立目录，并给每轮使用单独的输入副本、日志和结果文件。命令参数与首轮脚本一致：

```powershell
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$argLine = '"<本轮目录>\<案例>.run1.sxi" -silent -threads 8 -log "<本轮目录>\<案例>.run1.log" -calc -close'
$timer = [Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $exe -ArgumentList $argLine -WindowStyle Hidden -PassThru
$proc.WaitForExit()
$timer.Stop()
```

将路径中的占位符换成对应案例和本轮独立目录；`run1` 再换为 `run2`、`run3`。对 `aircraftorg`、`Torpedo Case`、`wbend`、`wbT2fix` 各运行三次。每次记录：

- 进程退出码；成功运行应为 `0`。
- 从日志读取 `Simulation time: ... secs` 和 `Total execution time: ... secs`。
- 用进程启动到退出的 `Stopwatch` 时间记录总等待时间；它包括进程启动、输入转换、计算和结果保存，不等于日志中的仿真时间。
- 确认生成非空 `.sxo`，并在可读取的结果摘要中核对 `ResultSummary.NREP = 1000`。
- 按 `1000 / Simulation time` 计算样本/秒。每个案例分别报告三次原始值和中位数；不要将不同案例的吞吐量直接排列为模型效率名次。

后续若要比较版本或机器，应在两组使用相同输入指纹、SIMLOX 版本、线程数、结果收集配置和重复次数；分别报告仿真时间、程序报告的执行时间和外部墙钟等待时间。记录环境变化和每次的退出状态。原实验没有单独设置预热轮次；新增预热时要明确标记，不与原协议混算。

## 已有结果

以下仿真时间来自首轮报告和 2026-09-25 的四案例复跑 `timings.json`。两轮都各对每个案例运行三次，参数为 1000 次重复仿真、8 线程；复跑 12 次均退出码为 0，日志均记录了仿真时间。

| 案例 | 2026-09-24 首轮中位数 | 2026-09-25 复跑三次 | 复跑中位数 | 首轮报告样本/秒 |
|---|---:|---|---:|---:|
| `aircraftorg` | 0.91 秒 | 0.77 / 0.78 / 0.78 秒 | 0.78 秒 | 1099 |
| `Torpedo Case` | 0.57 秒 | 0.44 / 0.45 / 0.45 秒 | 0.45 秒 | 1754 |
| `wbend` | 0.66 秒 | 0.51 / 0.52 / 0.52 秒 | 0.52 秒 | 1515 |
| `wbT2fix` | 0.65 秒 | 0.48 / 0.48 / 0.48 秒 | 0.48 秒 | 1538 |

四个案例均成功复跑，但第二轮仿真时间低于首轮中位数，外部墙钟时间也更短；因此现有证据支持“案例在该机上可重复运行”，不支持“精确复现首轮耗时”。当前没有对时差归因。首轮报告的总等待中位数约为 2.7–2.9 秒；第二轮每案例三次墙钟中位数约为 1.3–1.6 秒。

## 失败案例与解释边界

- `Tutorial SIMLOX case` 规模为 73 辆车辆，包含 210 类部件和多种任务、保障资源。首轮 8 线程运行约 146.02 秒后以 `-1073741819`（`0xC0000005`）崩溃；后续运行没有有效日志或结果。它没有可报告的吞吐量，且不属于本次四案例复跑。
- `Torpedo Case` 的地图图层无法读取，并触发 200 MB 百分位统计内存上限警告；`wbend` 也有百分位统计缺失和 `ESS with incomplete repair` 警告；`wbT2fix` 有 `ESS with incomplete repair` 警告。计时代表记录中实际运行的这些设置和结果收集条件。
- 各案例仿真时长、模型规模和统计粒度不同，跨案例样本/秒只用于描述各自 SIMLOX 示例负载。它们与本项目的 F35 canonical benchmark、Rust runtime 或 MLIR 试点没有输入/语义配对关系。
