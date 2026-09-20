# O4b 候选：按 mission 索引 active preflight（未收录）

候选源码提交：`838e6bc7adfb350984ef350b1053388f5f597552`。固定对照为已收录 O4a
提交 `1f394ba5303d3ddd0f47c30935cf1b241c649e15`。候选代码已由
`c3e84cb` 回退；本目录保留原始报告和候选构建身份。

## 实现与语义验收

- 候选按 mission 维护 active preflight job index 集合，替换 commissioned count 与取消路径对
  全部历史 jobs 的筛选；集合按 job index 排序，保持原取消顺序。
- 创建、waiting/running 切换、完成、零步骤完成和取消均维护索引；debug 构建会从 jobs 重建
  并断言一致。缺失或越界 mission 在 job 序列、状态和事件写入前显式失败。
- aircraft 仍经 HashSet 去重；取消仍先释放运行中资源，备件预约仍由下一分钟
  `transport_arrivals` 归还。定向测试覆盖跨 mission 隔离、重复飞机、历史作业、状态转换、
  commissioned active→prepared 接替、有序取消与只归还一次。
- fmt、全特性 check、clippy、17 项 Rust 测试及重建绑定后的 31 项 Python/Rust conformance 与
  differential tests 均通过。O4a/O4b 两轮报告的 RNG、完整 trace、metrics、终态、时间、
  停止原因与身份精确一致。

## 未插桩墙钟

每个单元为 O4b 6 次执行的“中位数 / 均值 / 最小值–最大值”。

| seed | 首轮 full | 首轮 summary | 确认轮 full | 确认轮 summary |
|---:|---:|---:|---:|---:|
| 0 | 0.238241 / 0.243351 / 0.232381–0.274468s | 0.225312 / 0.227251 / 0.222734–0.233232s | 0.232846 / 0.233334 / 0.232304–0.236091s | 0.224521 / 0.224281 / 0.222823–0.226229s |
| 1 | 0.204302 / 0.204647 / 0.203934–0.205700s | 0.197472 / 0.196896 / 0.193556–0.199933s | 0.202331 / 0.202339 / 0.201157–0.203648s | 0.194168 / 0.194424 / 0.193179–0.196789s |
| 7 | 0.164573 / 0.168168 / 0.163333–0.184439s | 0.155430 / 0.155357 / 0.152970–0.157598s | 0.163539 / 0.163519 / 0.161469–0.165534s | 0.152300 / 0.152743 / 0.151398–0.154868s |

相对 O4a 的固定报告，首轮六个单元的中位变化为
`+2.48% / +2.39% / +1.26% / -0.09% / +1.33% / +0.23%`，确认轮为
`+0.92% / +0.54% / +0.33% / +0.87% / +1.19% / +2.38%`；正值表示 O4b
更快。所有变化都低于约 5% 工程筛选线，且首轮 seed 1 summary 有 0.09% 回退，因此不称为
明确执行提速，也不再为收录追加复杂度。

## 机制与 profile

seed 0 的机制计数为：

| 计数 | 数值 |
|---|---:|
| active preflight lookup calls | 33,081 |
| 旧历史 job 暴露估计 | 7,214,145 |
| 实际 bucket candidate visits | 25,700 |
| cancel 历史暴露估计 | 7,492 |
| cancel candidate visits | 7 |
| active preflight jobs peak | 6 |

full 的 `preflight_generation` 中位数由 O4a 的 17.588ms 降至 12.935ms，summary 由
16.647ms 降至 12.134ms，说明索引确实消除了目标扫描。full 插桩分钟循环只从
280.736ms 变为 279.514ms；`resource_dispatch` 仍约 102.574ms，是主要热点。候选减少约
4–5ms 的 preflight phase 成本，但没有形成达到收录线的整体收益。

## 结论与范围

O4b 语义正确、目标计数和 phase 有改善，但实现增加按 mission 集合、状态维护、验证和测试，
整体墙钟只呈 0%–2.5% 小幅趋势。按优化计划的复杂度/收益门槛，候选已回退，不叠加 preventive、
运输或 mission 时间集合。F35 没有 shipment/预约返还负载，这些路径仍不能从本实验推导收益。

## 文件

- `f35-observation-interleaved-seeds-0-1-7.json`、`f35-observation-confirmation-seeds-0-1-7.json`：两轮 O4b 未插桩报告。
- `f35-seed0-full-profile.json`、`f35-seed0-summary-profile.json`：候选 profile 与机制计数。
- `host-manifest.json`：候选环境与工具链。
