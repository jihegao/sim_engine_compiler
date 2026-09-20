# O2a 候选：按飞机索引 preventive cycles（未收录）

候选源码提交：`c072639a1d754372a10dd4841d9320671f81a277`。固定对照为 O3 提交
`9400f0f21030cf7f5cec930df84f055109674c70`。候选将 preventive cycles 按飞机保留 Plan
顺序索引，并新增实际候选访问计数；31 项差分及定向顺序/重置测试均通过。

## 计数与内部 profile

- 旧 `preventive_scan_items=8,813,646` 被保留为可比的全 Plan 暴露估计。
- 候选实际 `preventive_candidate_visits=845,507`，按该计数减少约 90.4%。
- seed 0 full 插桩的 preventive generation 中位数由 O3 的 18.494ms 降至 18.083ms；总插桩
  执行中位数由 0.280495s 变为 0.288989s。
- O1/O3/O2a 的 seed 0 full `result_sha256` 均为
  `aa6e7ca01d2cb4044e1664a4ab27f476f0f4d1aefcefde93bdca1cc1f5d5f4d2`。

## 未插桩墙钟结论

相对固定 O3 候选，首轮三个 seed 的 full 中位数变化为 `+2.54% / +1.88% / +0.87%`，
summary 为 `+3.74% / +0.99% / +0.16%`；确认轮 full 为 `+0.06% / +3.05% / +2.09%`，
summary 为 `-0.08% / +1.30% / +1.83%`。正值表示 O2a 更慢。

候选没有在两个轮次、三个 seed、两个观测级别上形成可重复收益。减少候选访问没有转化为墙钟收益，
且索引仍按每个 Runtime 构建。按优化计划的收录门槛，提交已由 `a8b443e` 回退；本目录保留失败
实验与原始数据，后续不在 O2a 上叠加 O4。

## 文件

- `f35-observation-interleaved-seeds-0-1-7.json`：首轮 36 次记录。
- `f35-observation-confirmation-seeds-0-1-7.json`：确认轮 36 次记录。
- `f35-seed0-full-profile.json`、`f35-seed0-summary-profile.json`：内部计数与配对计时。
- `host-manifest.json`：候选环境与工具链。
