# AMD128 独立复测

本轮在 AMD128（Threadripper PRO 3995WX，64C/128T，125 GiB）上复测 O7。基线与候选分别从
clean `7563ca5` 和当前 O7 candidate 同步到隔离目录，使用独立 target 构建。两侧 source bundle
SHA-256 分别为：

- O6：`ea87511ca8245ea140af2568a9788d07a1ca302ca7ad6473ddd438e7a1864b03`
- O7：`ad4dd38c0fa404f5b8836b3abdc38068239b4bffa46817de91c9dfe4da0a91ec`

Plan 文件 SHA-256 为
`7c1347f2166bc8bf69bba53f5e25e5ae37b2dce965e37d123f8ffc2c59f8ac22`，fingerprint 为
`7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。12 份正式报告的构建、
Plan 和结果身份全部通过检查；对应记录的 result、sample request、trace、metrics、终态、停止时间
与原因均一致，校验错误为 0。

## 协议与环境限制

- 固定到 CPU 50（物理 core 50；SMT sibling 114），不与另一侧并发。
- 两个 measurement block；每个 block 开始时分别对两侧执行 seeds `0,1,7` 的丢弃预热。
- 6 个 paired sessions，顺序为
  `O6→O7, O7→O6, O6→O7 | O7→O6, O6→O7, O7→O6`。
- 每侧每个 session 运行 `seeds 0,1,7 × repeats 6`，同时交错 full/summary。
- 主机为 `schedutil` 动态频率，boost 开启；快照中的 CPU 50 瞬时频率为 2.2–4.25 GHz。
  FastLink、Gazebo、GNOME 等后台进程未停止，因此这是固定 CPU 的动态频率复测，不是严格固定功耗基准。
- 仓库固定的 Rust 1.90.0 在 AMD128 上未安装，主机 DNS 又无法访问 rust-lang/crates.io。本轮把
  本机锁定依赖 vendor 到远端，以 `--offline --frozen` 构建；两侧统一使用已安装的
  `rustc 1.98.1 (48a229cea 2026-09-01)`。报告没有把该环境冒充为 1.90.0。

## 结果

下表先在每个 session 内分别取 6 次中位数，再给出相对 O6 的改善。最后一列是 6 个 session
改善率的中位数与 MAD。

| 单元 | S1 | S2 | S3 | S4 | S5 | S6 | 跨 session 中位 / MAD | 正向 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| seed 0 full | 3.74% | 2.78% | 3.75% | 2.61% | 2.80% | 3.24% | **3.02% / 0.32%** | 6/6 |
| seed 0 summary | 3.65% | 4.21% | 3.41% | 2.84% | 2.87% | 3.11% | **3.26% / 0.39%** | 6/6 |
| seed 1 full | 3.23% | 2.47% | 2.57% | 3.01% | 2.07% | 2.08% | **2.52% / 0.45%** | 6/6 |
| seed 1 summary | 4.52% | 2.19% | 2.70% | 2.17% | 4.13% | 1.82% | **2.45% / 0.45%** | 6/6 |
| seed 7 full | 1.18% | -0.30% | 0.42% | 0.55% | 0.87% | 0.26% | **0.48% / 0.30%** | 5/6 |
| seed 7 summary | -0.25% | 0.05% | 2.78% | 1.66% | 1.54% | -1.54% | **0.80% / 0.96%** | 4/6 |

合并 36 个正式样本后的中位绝对时间仅用于量级检查：

| 单元 | O6 | O7 | 改善 |
|---|---:|---:|---:|
| seed 0 full | 359.299 ms | 347.318 ms | 3.33% |
| seed 0 summary | 342.232 ms | 330.517 ms | 3.42% |
| seed 1 full | 321.388 ms | 312.889 ms | 2.64% |
| seed 1 summary | 305.900 ms | 297.093 ms | 2.88% |
| seed 7 full | 290.733 ms | 289.417 ms | 0.45% |
| seed 7 summary | 272.440 ms | 270.666 ms | 0.65% |

36 个 side/session/单元的最大 within-session relative MAD 为 1.3576%，低于 2% 作废线；正序与
反序分层的跨 session 中位数都没有方向反转，最大层差为 1.9562 个百分点。尽管单场噪声和顺序
门槛通过，所有六个单元仍均低于 5% 目标；seed 7 还出现负 session，且 summary 的 MAD 大于
其中位改善。按复测前设定的门槛，O7 **未通过整体性能
验收，暂不收录**。该结论不否定已验证的 clone 计数和 resource dispatch phase 改善；它只说明
这部分局部收益不足以在 F35 三个 seed 的整体墙钟上形成稳定且有意义的增益。

## 证据文件

- `host-manifest.json`：主机、工具链、CPU、后台负载、Plan 与源码文件身份。
- `o7-source.diff`：本轮基线与候选的 runtime 差异。
- `identity-{o6,o7}.json`：构建和源码束身份检查。
- `formal/session-{1..6}-{o6,o7}.json`：12 份正式原始报告。
- `formal/warmup-block-{1,2}-{o6,o7}.json`：丢弃预热。
- `formal/snapshot-*.json`：block/session 前后的负载与 CPU 频率快照。
- `formal/report-sha256.txt`：远端正式报告摘要。
