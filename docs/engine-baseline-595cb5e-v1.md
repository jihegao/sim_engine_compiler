# 引擎基线与采用状态：595cb5e / v1

任务 `engine-baseline-595cb5e-v1`，核对日期 2026-09-27。本文件是当前状态
说明，不是新性能测量，也不重写历史报告的原始数据或当时决定。

## 冻结版本与验收身份

- compiler main：`595cb5eee9987324b19a8c3566f201f937e05f15`，tree
  `a33c3c089c37c9b6662f4e9aa2a40ab7ca12f429`。
- [main CI 36271508735](https://github.com/jihegao/sim_engine_compiler/actions/runs/36271508735)
  对应上述提交且成功；包括 Rust runtime/AOT/cache、PyO3、必需的 MLIR/O5
  无跳过组合及全量 Python 检查。CI 使用 Rust 1.90.0、Python 3.12、
  LLVM/MLIR 23.1.1；通过 CI 不代表任何性能门槛通过。
- Schelling 实现提交 `b3474872709cd3f298fbe5de7bd3d9e1cc94ecd1`
  与上述 main 的 tree 相同。其本地验收 CLI SHA-256 为
  `316eeb625a4297b580821cb836d2ce90dee876efbbc7db2770cbcaf033ea536e`，
  工具链 Rust 1.90.0 / Python 3.12.13。此二进制是该次构建产物，
  不是所有平台或当前所有安装的二进制身份。
- 配套 CSABench main `15c1f0dae6e82ca61abcfa277e821d5fd1485f93`：
  [main CI 36271512905](https://github.com/jihegao/CSABench/actions/runs/36271512905)；
  [九例差分与逐例 Plan/tape 身份](https://github.com/jihegao/CSABench/blob/15c1f0dae6e82ca61abcfa277e821d5fd1485f93/reports/schelling_handcase_differential_v1.json)
  及同目录的完整 runs 文件绑定输入、Plan 指纹、oracle、二进制、验证器。
  这是受控初态/顺序/随机值的有限语义证据，不是 setup 分布、原生 PRNG
  或完整源模型等价验收。

## PreparedBatchPlan：实现采用不等于性能门槛通过

[PR #9](https://github.com/jihegao/sim_engine_compiler/pull/9) 已合并为
`ceb8d1b5dbd14e028bbb8c96b0e3027a03ac7889`，是本基线祖先。
其 PR 描述和 [J35 历史报告](../benchmarks/batch_preparation/results/amd128-j35-20260926/REPORT.md)
中的“保留草稿 / 未合并为默认”描述的是当时建议，**已不能描述当前代码状态**。
这不是对历史性能结论的撤销，也没有发现可据以声称“门槛后来通过”的新测量。

当前调用链可直接从源码核对：

| 入口 | 实际路径与默认值 |
|---|---|
| Python `run_batch` | `native.py` → `rust/compiler/src/python.rs::run_batch_json` → `batch.rs::run_batch_from_slice_with_observation` → 每次调用建立一个 `PreparedBatchPlan` → `run_prepared_batch`；默认 `full`，候选派遣关闭，时间 profile 取传入 Plan |
| Rust `run_batch` / CLI `--seeds` | `run_batch_with_dispatch` 建立共享 preparation，样本用 `Runtime::from_prepared_with_observation`；不需要启用 preparation 开关 |
| Rust `run_prepared_batch` | 显式持有并复用 `Arc<PreparedBatchPlan>`，可跨多次批量调用；这不同于普通入口每次调用重新 preparation |
| canonical MC | `run_canonical_batch` 固定 `event-time-v2` + `summary`，按 Plan 分组调用 indexed batch，每组 preparation 一次；不是 Project JSON 解释器 |

实现见 [batch.rs](../rust/runtime/src/batch.rs)、[native.py](../src/sim_engine_compiler/native.py)、
[compiler Python 绑定](../rust/compiler/src/python.rs)（由 `pyproject.toml` 的 Maturin
manifest 选择；runtime crate 另有同类绑定）。线程数未指定时使用 available parallelism，
并以样本数封顶；不是自动选择历史性能较好的 1/2 线程。
共享对象仅含只读派生布局，RunState/RNG 仍按样本隔离，结果按 `sample_index`
排序。这里的 aircraft batch 结论不扩展为 ABM 使用同一 PreparedBatchPlan 的声明。
Python 公共 API 尚未暴露跨调用持久 handle；单样本 `Runtime::new` 也构造自己的
preparation，但不存在跨样本共享收益的推论。

**本次状态决定：**如实登记“已合并、普通 aircraft 批量默认经过共享 preparation；
原 J35 全线程性能收录门未通过；595cb5e 的性能尚未测量”。本次不自动回退
运行路径，不增加开关，不追认当时门槛已通过，也不承诺当前版本有历史加速比。
若要改变采用策略，应另开带语义回归和新测量的决策，不用文档暗改默认行为。

### 原性能门槛保持原样

[实验规则](../benchmarks/batch_preparation/README.md)要求至少六个配对、每对收益为正、
中位收益 ≥5% 且超过两臂各自相对 MAD、RSS 中位比 ≤1.05 且超过 1.05 的配对少于两次；默认采用要求
J35 O5 + Summary 在 32 和 256 样本、1/2/4/8 线程范围都满足。

| 历史 indexed-scan Summary | 1 线程 | 2 线程 | 4 线程 | 8 线程 |
|---|---:|---:|---:|---:|
| 32 样本配对中位收益 | 7.94% | 6.62% | 3.89% | 0.11% |
| 256 样本配对中位收益 | 7.97% | 6.96% | 4.83% | 1.01% |
| 两个样本量均达原门槛 | 是 | 是 | 否 | 否 |

以上属于 **e9b6391 对 d4c18e8 的历史 AMD128 实测**，不是 595cb5e 实测。
candidate dispatch 当时仍慢于 indexed scanning；共享 preparation 不意味着启用
candidate dispatch。Full、Python 绑定、诊断计数、hot handle 的边界各自独立，
不能相加或替代 cold CLI 默认采用门。历史 hot v1 的 `serialize_ns` 包含两次
序列化，单次输出成本仅可使用修正后的 hot v2 证据。

### 历史测量身份（保留，不重生成）

权威清单为 [cold-summary/identity.json](../benchmarks/batch_preparation/results/amd128-j35-20260926/cold-summary/identity.json)
和 [source/manifest.json](../benchmarks/batch_preparation/results/amd128-j35-20260926/source/manifest.json)。

| 身份 | 固定值 |
|---|---|
| 上游 Project revision | `0e709bdcc2d692d9cfed49b9037c76ef71aefe33` |
| Project SHA-256 | `dd37321d012145b3b1554f23f58bca4d70843bfd49cc22233d4969be2f247569` |
| canonical input SHA-256 | `ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793` |
| scan Plan 文件 SHA-256 | `bcc161c53821002026e9d04bd4b88dd8b5b19b9aaf9dd4039fcd2d25ce561b2e` |
| indexed Plan 文件 SHA-256 | `e31fa22cb22451808a1eb3846b560ad51cb0b8b75418800ab3732c2857c9be17` |
| 两 Plan 的语义指纹 | `d510e74f5ae4a10ff2bae01457879e4fc43bc8576a394f96314220243cb0778c` |
| baseline revision | `e9b6391fffd918e0f6e742bd1ef0e1312921b769` |
| candidate revision | `d4c18e8a5fdd3be46e9862bcd0df1eb1cf29eaaa` |
| baseline CLI SHA-256 | `8cb8388037c4a031dc51e0f430717206438c7cd73e67dd5f2a0650e2bd13826f` |
| candidate CLI SHA-256 | `9c6a8800ef0f0b5f4c801235d52e7bb0a101d1b528eea512f6b0f61d3f04a03b` |
| runtime / driver | Rust 1.98.1 / Python 3.10.12；AMD128 64 物理核，1 NUMA |
| profile / seeds | `event-time-v2` / `legacy-sequential-v1`；`0,1,7,7` 重复 |

hot v2 独立源版本是 `6b8a6b7fcf4c7f43df20b4d137b31b97f5fe64d8`，
其 benchmark binary SHA-256 为
`d9ab88001949e4dcc89fb55213e9dbd3ab15ae53d94e3331039b303d6df8c8fd`；
不能与上述 cold candidate 混写。旧 oracle 的零备件需求 `spare_fill_rate=null`
与 Plan `1.0` 差异依然保留，历史比较明确排除该未定义 0/0 指标。

## 当前能力与开关矩阵

下表均描述冻结的 595cb5e；链接给出范围证据，不把曾有性能收益解释为当前收益。

固定合同版本：aircraft Business `aircraft-business-ir/v1`、Core
`simulation-core-ir/v2`、Plan `aircraft-support-plan/v1alpha2`、AOT
`aircraft-support-aot/v1alpha5`、cache `sim-engine-plan-cache/v3`；兼容工作策略
`stable-topological-serial`、RNG `legacy-sequential-v1`。ABM 使用独立的
`abm-business-ir/v1`、`abm-core-ir/v1`、`abm-tick-plan/v1` 和
`abm-random-tape/v1`，不据此宣称 aircraft 已切换为具名随机流。

| 能力 | 当前入口 / 默认 | 已验证范围 | 实验性或未验证边界 |
|---|---|---|---|
| Aircraft 三层 IR / Python / Rust | canonical → Business → symbolic Core → Plan；Python compile API/`compile_execution_plan.py` 默认 `legacy-minute-v1`，Rust AOT CLI 默认 `event-time-v2` | [三层 IR](three-layer-ir.md)、B1/B2/B3、F35 0/1/7，main CI | 有限粗粒度兼容操作，不是通用领域解释器 |
| O5 | Plan 显式 `event-time-v2`；canonical MC 固定启用 | [语义基线](semantic-baseline.md)、F35 full/summary 差分 | persistent callbacks / microstep convergence 未实现；O5d 未合入 |
| PreparedBatchPlan | 普通 aircraft batch 默认采用；Rust 可显式复用 handle | 严格校验、隔离、重复 seed/排序/线程回归；main CI | J35 原全线程性能门失败；当前性能未测 |
| MLIR v2 资源索引 | 编译时选择 MLIR 入口；Plan 带索引才有缓存路径 | [依赖派遣](dependency-dispatch.md)、main 必需 MLIR/O5 CI | 索引不是 candidate dispatch 开关；历史收益非当前收益 |
| candidate dispatch | CLI `--dependency-dispatch` / Rust bool 显式开启；Python 普通 batch 未暴露该开关 | 适用 v2 完整索引、结果/错误路径差分 | 默认关闭，尚无普适性能采用结论 |
| Rust AOT / Plan cache v3 | 独立 AOT / cache 入口；canonical MC 可给 cache_dir | [输入校验](strict-work-input-validation.md)、AOT/cache CI | cold-start v2 历史数字不能用于 v3；无 Rust Project Adapter |
| Full / Summary | 普通 native/runtime CLI 默认 Full；Rust AOT CLI 默认 Summary，canonical MC 固定 Summary | 随机请求、业务指标与终态对照 | Summary 不保留完整 trace，不能给完整执行解释 |
| ABM tick / source extension | `abm-tick-v1` 独立 registry；`abm-source-semantics/v1` 可选 | [source semantics](source-semantics-v1.md)、手算/严格 tape/Python-Rust 差分 | Schelling source gold、setup/200-run 分布未验收；无通用 NetLogo importer |
| lineage / trace | 已有 `compiler-lineage/v2`、impact 与 Full 事件来源字段 | [三层 IR](three-layer-ir.md)及现有 tests | #10/#11 公共审阅/运行身份合同、有界查询与完整性声明尚待实现 |

当前 main CI 未替代在 595cb5e 上重新执行完整 J35 上游 oracle；该三 seed
领域证据仍绑定历史 candidate。也没有 595cb5e 的 J35 性能二进制或 RSS 实测。

## 下一切片与实验边界

1. **#10/#11 先冻结公共身份合同**：复用 business ID、Core symbol 和 lineage，
   明确输入层/修订/Plan 指纹与 bundle 一致性；重复 seed 用 run/sample 身份区分；
   事件身份不得来自过滤后的行号。缺层、修订冲突、缺 lineage 或未采集必须
   返回结构化未知/证据不足，不能猜测来源或以前一事件冒充原因。
   首个切片只做合同、确定性验证与有限 fixture，不提前混入 SysML renderer、
   新事件调度器、采集默认开关或 Cloud UI。
2. **#6 另开冻结版本实验**：先在指定版本通过语义差分，再固定源码、输入/Plan、
   二进制、工具链、profile、seed/sample_index、观测级别、主机拓扑与负载。
   以相同样本比较 1/2/4/8 线程及 scan/cache/candidates；区分冷 CLI、热 handle、
   Python 绑定，分别记录编译、加载/校验、初始化、执行、序列化、写盘、RSS。
   复用原实验 driver 但写新目录，禁止覆盖历史证据。正式计时避免与开发/测试争用。
3. **SIMLOX 仍为外部验证线**：4700-3 提供共同语义范围内的最小输入与首处分歧后，
   才判断配置、指标口径、领域规则或引擎缺陷；不为迎合结果默改 Python 基线。
   不同主机/模型耗时不能算引擎加速比。

本次只新增状态说明并链接 README/roadmap；不修改 AGENTS.md（PR #16 独立）、
runtime、历史报告、原始记录或任何默认开关。不关闭 #6/#10/#11。
