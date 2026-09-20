# F35 执行热路径与观测隔离

状态：2026-09-20 已完成观测隔离、O1/O3/O4a/O6 收录及 O2a/O4b 回退决策。固定输入为 F35 43 天 Execution Plan，fingerprint
`7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。语义差分覆盖
seeds `0、1、7`；墙钟与内部 profile 使用 seed `0`，不把单 seed 的耗时分布外推为所有案例。

## 结论

主要成本不是完整 trace。`summary` 确实没有构造 trace 事件 JSON，但交错运行的六组
`full/summary` 执行时间基本重叠：

| 观测级别 | 未插桩执行中位数 | 六次均值 | Result JSON | trace 事件 |
|---|---:|---:|---:|---:|
| `full` | 2.629 s | 2.634 s | 4,212,927 bytes | 10,670 |
| `summary` | 2.605 s | 2.633 s | 1,392,096 bytes | 0 |

`summary` 的中位数低约 `0.9%`，但六次均值只低约 `0.03%`，逐对比值范围为
`0.985–1.026`；当前证据不能宣称有稳定执行加速。它把单样本结果大小减少约 `67%`，
因此仍然显著降低后续序列化、跨语言传输与持久化负担。

内部插桩进一步确认观测隔离：两级别都有 10,670 次业务事件尝试，`full` materialize
10,670 个事件和 52,286 个字符串值，`summary` 两项均为 `0`。`full` 的事件构造累计
约 `8.79 ms`，只占插桩执行时间约 `0.33%`。RNG 为 3,876 次请求，生成器调用累计约
`0.11 ms`；metrics 构造约 `0.014 ms`，终态构造约 `0.60 ms`。这些子计时只覆盖明确
包围的调用，不把其上层 phase 的扫描或调用点预备工作重复归因。

## Phase 与内部计数

`full` 五次插桩中位数为 2.693 s。主要 phase 的直接墙钟占比为：

| Phase | 中位累计时间 | 执行占比 |
|---|---:|---:|
| `preflight_generation` | 724.2 ms | 26.89% |
| `mission_dispatch` | 712.7 ms | 26.46% |
| `mission_success` | 709.8 ms | 26.36% |
| `failures` | 269.9 ms | 10.02% |
| `resource_dispatch` | 112.0 ms | 4.16% |

前三个 phase 合计约 `79.7%`，都在逐分钟扫描任务；加入 failures 后约 `89.7%`。
单样本内部计数为：

| 计数 | 次数 |
|---|---:|
| 分钟循环 | 61,920 |
| mission 扫描项 | 19,319,040 |
| job 扫描项 | 49,410,043 |
| component 扫描项 | 19,275,687 |
| preventive 扫描项 | 8,813,646 |
| Plan spec 克隆 | 19,778,872 |
| 已插桩 Map 读取 | 39,584,579 |
| 已插桩 Map 写入 | 19,271,774 |

Map 数字只统计运行时显式标记的索引 Map 访问，是可比较的下界，不包含集合实现内部访问。
系统采样火焰图与直接计时结论一致：在 `run_internal` 样本中，`String::clone` 的 inclusive
样本约 `27.9%`，`MissionSpec::clone` 约 `21.6%`，`BTreeMap::insert` 约 `13.1%`；
`Runtime::emit` 约 `0.8%`，所有可见 `serde_json` 栈约 `1.5%`。这些 inclusive 比例互相
重叠，不能相加，也不替代上面的直接 phase 计时。

因此下一轮低风险优化应优先：去掉逐分钟 `MissionSpec`/字符串克隆、预计算任务和资源
索引、把高频 failure remaining 状态从树 Map 移到索引数组。事件时间跳跃仍排在这些
优化之后，并继续受同分钟 phase 与全部 differential tests 约束。

后续工作包、代码位置、语义边界与基准门槛见
[观测隔离与 F35 热路径优化计划](../../docs/performance-optimization-plan.md)。O0/O1 已完成实现与
语义验收；本页以下 `20260920` 数字仍是优化前已保存基线，候选性能须由新报告单独证明。

O1 候选结果见 [`results/20260920-o1-50857fe/README.md`](results/20260920-o1-50857fe/README.md)：
三个 mission phase 的逐项深拷贝已消除，两个独立候选轮次均复现约 0.44–0.49s 的中位执行；
更新后的主要成本为 failures 和 resource dispatch。与旧基线的倍数比较受旧二进制身份缺失限制。

O3 候选结果见 [`results/20260920-o3-9400f0f/README.md`](results/20260920-o3-9400f0f/README.md)：
故障倒计时已迁移为每架飞机的稀疏数组，相对固定 O1 候选在两个轮次、三个 seed、两个观测级别
均有明确收益；更新后的主要成本为 resource dispatch，随后是 failures 和 preventive generation。

O2a preventive 索引实验见 [`results/20260920-o2a-c072639/README.md`](results/20260920-o2a-c072639/README.md)：
实际候选访问虽减少约 90%，但两轮墙钟没有可重复收益，候选已回退，未叠加到后续优化。

O4a waiting/running 活动集合见 [`results/20260920-o4a-1f394ba/README.md`](results/20260920-o4a-1f394ba/README.md)：
四组同会话 O3/O4a 固定二进制对照的 24 个单元中 23 个正向，各 seed/观测组合跨会话中位改善
为 5.20%–6.76%。收益主要来自 job progress；resource dispatch phase 仍约占 36%，只呈小幅趋势。

O4b active-preflight 实验见 [`results/20260920-o4b-838e6bc/README.md`](results/20260920-o4b-838e6bc/README.md)：
目标候选访问由旧历史暴露估计 7,214,145 降至 25,700，preflight phase 约减少 4–5ms，
但两轮整体墙钟仅约 0%–2.5% 变化，候选已回退。

O6 compiled steps 见 [`results/20260920-o6-4508860/README.md`](results/20260920-o6-4508860/README.md)：
resource dispatch/job progress 改用派生只读 step layout，Plan spec clone 计数由 459,832 降至
153,010。四组 O4a/O6 固定二进制对照的 24 个单元全部正向，各 seed/观测组合跨会话中位改善
为 11.09%–18.17%；完整结果哈希精确一致。该轮不包含 dense inventory，也未测量完整
PreparedPlan 的初始化、批吞吐与内存收益。

O5 `event-time-v2` 第一阶段见 [`results/o5-event-time-v2-20260921/README.md`](results/o5-event-time-v2-20260921/README.md)：
在独立 semantic profile 下按业务唤醒跳过空分钟，并在唤醒分钟执行原 canonical phase 表。
F35 seed 0 的 61,920 分钟降为 1,609 个唤醒；三 seed、full/summary 和边界案例精确等价。
AMD128 两个稳定会话的各组合跨会话中位改善为 69.74%–81.62%。当前仍会重建日历并逐 tick
推进故障暴露，不是 persistent callback scheduler。

## 原始证据

- `results/f35-observation-interleaved-seed0-20260920.json`：交错 `full/summary` 未插桩墙钟、
  结果大小和业务/RNG 哈希。
- `results/f35-seed0-{full,summary}-20260920.json`：内部 phase、事件、RNG、扫描、克隆和
  Map 计数。
- `results/f35-seed0-{full,summary}-20260920.sample.txt`：macOS `sample` 原始调用树。
- `results/f35-seed0-{full,summary}-20260920.folded`：折叠栈。
- `results/f35-seed0-{full,summary}-20260920.flamegraph.svg`：可交互 SVG 火焰图。

环境为 macOS 26.6.2 arm64、10 logical CPU、Rust 1.90.0。系统采样构建启用 debug
symbols 和 `profiling` feature；该 feature 只阻止关键 phase 被内联，以保留火焰图函数名，
正式未插桩墙钟不启用它。

上述 2026-09-20 原始记录仍是 v1 报告，未保存可执行文件或源码束摘要。新生成的 v2 报告
会保存可执行文件 SHA-256、编译时嵌入的 runtime/benchmark 源码束 SHA-256、源码文件清单、
Cargo manifest/lock/toolchain、构建 profile/features、目标平台与 Plan 文件 SHA-256。这样即使
工作树为 dirty，也能判断两个报告是否来自同一批关键源码和同一二进制。Git revision、工作树
状态和 rustc 完整版本不由基准进程在运行时调用 shell 推断；需要这些标签时，在构建前设置
`SIM_ENGINE_SOURCE_REVISION`、`SIM_ENGINE_SOURCE_TREE_STATE` 和
`SIM_ENGINE_RUSTC_VERSION`。未设置时字段为 `null`，源码束和二进制摘要仍会记录。若需保存
完整 dirty diff 和 OS 版本/CPU/内存等主机信息，先在基准外生成并保留证据文件，再分别通过
`--source-diff`、`--host-manifest` 传入；报告记录路径、字节数和 SHA-256，但不会替调用方生成
或复制这些文件。源码束只覆盖报告列出的 Rust runtime/benchmark 关键文件，不等价于完整工作树。

`hot_path_profile` v2 在每一轮对插桩/未插桩结果做字段级检查：`full` 要求完整 trace 和所有
非 trace 字段相同；`summary` 要求所有非 trace 字段相同，并要求两边 trace 都为空。报告同时
保存完整 result、trace、RNG、metrics 和终态摘要，以及 time、stop reason 和结果身份，便于
离线复核。`observation_benchmark` v2 也显式拒绝 summary 产生 trace，并比较 Plan 身份与 seed。

## 复跑

交错观测级别墙钟：

```bash
cargo run --release --manifest-path rust/runtime/Cargo.toml \
  --bin observation_benchmark -- \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json \
  benchmarks/hot_path/results/f35-observation-interleaved-seed0-20260920.json \
  --seeds 0 --repeats 6
```

内部 profile：

```bash
SIM_ENGINE_SOURCE_REVISION="$(git rev-parse HEAD)" \
SIM_ENGINE_SOURCE_TREE_STATE=dirty \
SIM_ENGINE_RUSTC_VERSION="$(rustc --version)" \
cargo run --release --manifest-path rust/runtime/Cargo.toml \
  --bin hot_path_profile -- \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json \
  /tmp/f35-full-profile.json --seed 0 --observation-level full --repeats 5 \
  --source-diff /path/to/retained-source.diff \
  --host-manifest /path/to/retained-host-manifest.json
```

观测隔离语义验收：

```bash
uv pip install --python .venv/bin/python -e .
.venv/bin/python -m unittest tests.differential.test_rust_runtime -v
.venv/bin/python -m unittest tests.differential.test_python_binding -v
```

差分用例覆盖 B1/B2/B3 synthetic 切片与 F35 seeds `0、1、7` 的两个观测级别、截断
horizon，以及 `[7,0,7,1]` 在 1/3 线程批量路径上的顺序、重复 seed 和观测隔离。绑定测试
现在要求 native extension 已安装，缺失会失败而不是整类跳过。以上是语义验收。O6 已保存
固定基线/候选二进制的 v2 paired 报告；两个独立二进制的交错调度仍未内建到工具本身，
正式优化对照继续由外部 runner 固定顺序并分别保留两边报告。
