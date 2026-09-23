# O7 候选：resource dispatch 重试路径克隆消除

固定基线为 `7563ca5`（O6 报告提交，runtime 源码与 `4508860` 相同）。候选是在该基线上的
单文件改动；基线/候选 source bundle SHA-256 分别为
`ea87511ca8245ea140af2568a9788d07a1ca302ca7ad6473ddd438e7a1864b03` 与
`ad4dd38c0fa404f5b8836b3abdc38068239b4bffa46817de91c9dfe4da0a91ec`。固定 Plan fingerprint
为 `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。

## 实现与语义边界

- waiting job 仍按 `(priority, started_time.unwrap_or(current_minute), job_id)` 排序，但比较器直接
  借用 `job_id`，不再为排序键复制字符串。
- supply route 仍按 Plan 顺序逐项重试，保留 destination、空 product 通配、capacity、库存与首条
  可行路线语义；扫描时只借用 route 并复制标量，只有实际发运时才复制 trace 所需字符串。
- `step.code` 只在作业确实取得人员、设备和备件并启动时复制；短缺/容量不足重试不再复制。
- 没有缓存“无库存/无可用路线”的结果。库存到达、取消返还和其他运行态变化后，下一分钟仍会
  重新检查 route。
- Plan、fingerprint、业务 ID、分钟 phase、RNG、资源结算、trace 与终态合同不变。

新增 `supply_route_candidate_visits` profile 计数，并加入零库存 route 连续重试回归：候选仍每次检查
route，但不增加 `plan_spec_clones`，短缺事件仍只在 signature 改变时输出。Rust 14 项单元测试、
3 项 profile 工具测试、clippy，以及重建 PyO3 后的 31 项 Python/reference/Rust conformance 与
differential tests 全部通过。

## 首轮固定二进制同会话对照

每个单元运行 6 次取中位数。A/C 先运行 O6，B/D 先运行 O7。24 个会话单元全部为正，paired
报告中对应 seed/观测的 `result_sha256` 精确相同。

| 会话 | seed 0 full | seed 0 summary | seed 1 full | seed 1 summary | seed 7 full | seed 7 summary |
|---|---:|---:|---:|---:|---:|---:|
| A | 10.10% | 10.90% | 9.29% | 8.84% | 4.04% | 3.63% |
| B | 10.37% | 11.22% | 7.37% | 7.80% | 5.92% | 4.12% |
| C | 9.88% | 10.29% | 8.13% | 8.40% | 2.93% | 3.95% |
| D | 10.72% | 11.64% | 9.33% | 9.28% | 3.43% | 2.32% |
| 跨会话中位 | **10.24%** | **11.06%** | **8.71%** | **8.62%** | **3.73%** | **3.79%** |

seed 7 的收益低于约 5% 目标，但首轮四组和两个观测级别均为正；该 seed 的短缺重试负载较小。
这些数据只构成候选证据，不单独构成最终收录。

## 独立重建复测：未通过整体墙钟门槛

审计后从 clean `7563ca5` worktree 与当前 dirty candidate 分别重新构建二进制，写入
`source_revision`、`source_tree_state`、`rustc_version`，并把 host manifest 以 SHA-256 绑定到
raw report。每个二进制先单独跑 seeds `0,1,7` 的丢弃预热，再执行两组反序 session；随后又以
一致的 retest manifest 重复两组。结果 hash 仍全部一致，但主机整体墙钟出现显著漂移：

| 会话 | seed 0 full | seed 0 summary | seed 1 full | seed 1 summary | seed 7 full | seed 7 summary |
|---|---:|---:|---:|---:|---:|---:|
| E | 15.17% | 13.20% | 6.59% | 9.50% | -5.42% | -8.92% |
| F | 12.47% | 7.80% | 11.23% | 13.96% | -1.46% | -1.03% |
| G | -18.43% | -17.80% | -6.29% | -14.42% | 42.02% | 33.56% |
| H | 38.63% | 39.22% | 31.07% | 34.35% | 4.87% | -3.71% |

绝对执行时间在这些 session 间约翻倍并随运行顺序剧烈摆动，说明当前机器会话不足以稳定归因
约 4% 的 seed 7 整体收益；G/H 甚至连 seed 0/1 的方向也受顺序影响。随后已转到 AMD128 做独立
复测，结果见下节。

## AMD128 固定 CPU 独立复测：仍未通过整体门槛

AMD128 复测使用隔离源码树/target、固定 CPU 50、两个 block 分别预热，以及 6 组正反各三次的
paired sessions。构建、Plan 和所有业务/RNG 结果身份校验均为 0 错误。seed 0/1 的六组均为正，
跨 session 中位改善为 2.45%–3.26%；seed 7 full/summary 仅 5/6 和 4/6 session 为正，中位改善
为 0.48% / 0.80%，其中 summary MAD 为 0.96%。所有六个单元都低于 5% 目标，seed 7 也未满足
低收益例外所需的 6/6 同向和噪声裕量。

因此 O7 当前状态仍为 **语义已验证、目标 phase 有直接改善，但整体性能未达到稳定收录门槛**。
代码保留为未提交 candidate，不得把局部 phase 改善或首轮 24/24 正向写成最终验收。AMD128 使用
动态 `schedutil`/boost 且有后台进程；两侧统一使用离线依赖与 rustc 1.98.1，未冒充仓库固定的
1.90.0。完整协议、逐 session 数字和原始文件见 [`amd128/README.md`](amd128/README.md)。

## 热路径与批量变化

seed 0 profile 各 5 次取中位数。插桩 phase 与未插桩执行不混算；这些数字只证明目标 phase 与
clone 计数发生预期变化，整体执行是否收录以上述独立复测失败结论为准。

| 观测 | 指标 | O6 | O7 |
|---|---|---:|---:|
| full | resource dispatch | 63.249 ms | 45.643 ms |
| summary | resource dispatch | 59.389 ms | 40.854 ms |
| full/summary | Plan spec clone 计数 | 153,010 | 4,289 |
| full/summary | O7 route candidate visits | 不可用 | 148,721 |

route candidate visits 与被消除的约 148,721 次 route spec clone 一致。resource dispatch phase 降低
约 28%–31%。Stage C seeds `0,1,7` 的 5 次中位数如下：

| 线程 | 指标 | O6 | O7 | 改善 |
|---:|---|---:|---:|---:|
| 1 | batch execution | 520.837 ms | 476.806 ms | 8.45% |
| 1 | end-to-end batch | 544.387 ms | 499.985 ms | 8.16% |
| 3 | batch execution | 266.144 ms | 222.910 ms | 16.24% |
| 3 | end-to-end batch | 291.042 ms | 260.768 ms | 10.40% |

Stage C 每轮 batch result hash 也保持一致。独立复测揭示主机调度/功耗噪声后，这些 Stage C
数字仅保留为首轮 supporting evidence，不作为收录依据，也不外推线性吞吐。

## 已回退的前置实验

在 O7 前先独立测试了 mission/aircraft 与 activity compatibility lowering。四组 fixed-binary
session 的单元变化范围为 -0.69% 到 +2.84%，没有达到收录线且有负单元，因此代码已完整回退；
未把该结构性候选与本轮 dispatch 优化捆绑。

证据副本中的本机临时路径已替换为占位符，进程快照命令行已省略；源差异仅规范化行尾空格。各 JSON 中的 source/host manifest 哈希指向随附的清理副本，原始哈希保存在 original_sha256 字段。AMD128 正式报告的 SHA-256 清单针对清理后的副本重新生成，并使用相对文件名。

## 文件

- `paired-{a,b,c,d}-o6.json` / `paired-{a,b,c,d}-o7.json`：固定二进制对照原始记录。
- `o6-seed0-{full,summary}-profile.json` / `o7-seed0-{full,summary}-profile.json`：phase 归因。
- `stage-{o6,o7}-t{1,3}.json`：单/三线程分段 batch 检查。
- `retest-{warmup-o6,warmup-o7,e-o6,e-o7,f-o6,f-o7}.json`：独立重建的预热与第二会话复测。
- `final-{warmup-o6,warmup-o7,g-o6,g-o7,h-o6,h-o7}.json`：绑定一致 retest manifest 的再次复测。
- `host-manifest.json` / `retest-host-manifest.json`：首轮与独立重建的主机、工具链、二进制、源码束与 Plan 身份。
- `amd128/`：AMD128 固定 CPU 六组 paired sessions、环境快照、源码差异和结论。

## 未完成项

- injected spare 的动态 requirement 仍会在每次重试时合并为临时 `BTreeMap`/`Vec`；应作为独立
  候选测量，不能把预期收益计入 O7。
- inventory / reservation 仍是字符串键 Map；F35 缺少静态 spare 正路径，dense layout 需另用
  有真实库存/运输负载的案例测量。
- 其他静态索引仍按 sample 构造；完整共享 PreparedPlan 需要单列 prepared build、per-sample init、
  batch throughput 与 RSS，不用 execution-only 基准代替。
