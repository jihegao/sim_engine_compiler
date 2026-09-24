# O5 与三层 IR 验证整合记录

日期：2026-09-24

集成分支：`codex/o5-mlir-integration-20260924`

基线：`main` / `origin/main` `ae36799bb1238c430a830c26c6bf9db985db2ce2`

吸收来源：`codex/event-time-v2-o5` `ed59f354df11d8855597e74099b75b5ea93acff1`，其中 PR #1 已合并的三层 IR 验证提交随该分支一并吸收。

## 范围与结论

本次从最新 `main` 整合 O5a 保守跳时和 PR #1 三层 IR 验证，保留 `main` 已有的 MLIR 资源派遣试点。没有整合 MC 接口、Rust AOT/缓存、四项业务语义修复，也没有把 O5d guarded continuous advance 实验候选接入运行时。原有 O5/O5d 报告、计时数据、来源清单与实验差异均保留；本文件只记录本次整合验证。

MLIR pass 现在接受 `legacy-minute-v1` 和 `event-time-v2`，并要求模块携带完全匹配的 canonical 15-phase 顺序。MLIR 编译入口新增 `--semantic-profile`，默认为旧 profile。组合回归对 F35 canonical 输入在索引开/关两条路径运行 Rust，并对 seeds `0、1、7` 比较完整 `RunResult`；三组均逐字段完全一致，索引的基础 Plan 身份也与未索引 Plan 相同。

这证明 O5 与 MLIR 索引在当前 F35 输入上的组合语义一致，不代表新的端到端性能结果，也不扩展至其他业务 profile 或输入。

## 验证结果

| 检查 | 结果 |
|---|---|
| Rust runtime `cargo test --locked --manifest-path rust/runtime/Cargo.toml` | 29 项通过：14 library、6 continuous-advance experiment、6 event-time benchmark、3 profile tests |
| `tests/differential/test_event_time_runtime.py` | 9/9 通过；包含旧语义、唤醒边界、F35 seeds 和 event-time profile 约束 |
| `tests/conformance/test_b1_reference.py` | 13/13 通过 |
| `tests/differential/test_mlir_resource_dispatch.py` | 6/6 通过；含 F35 三 seed 组合差分和下述 B3 四路径交互案例 |
| PR #1 三层 IR `run_cases.py` | 37/37 案例通过；Python reference、indexed Python 与 Rust 后端结果均执行 |
| PR #1 `test_review_fixes.py` | 9/9 通过 |
| PR #1 adversarial validation | 固定生成器生成 100 个模型，0 个差异；15/15 拒绝探针通过 |
| PR #1 legacy F35 检查 | 12/12 正例和 64/64 显式断言通过；保存的旧模型 oracle 对 seeds `0、1、7` 均无差异 |
| MLIR pass build | `cmake --build tools/mlir_dispatch/build-unix --parallel 2` 成功 |
| 旧来源 manifest | `verify_manifest.py` 核验 302/311；9 个条目因整合分支上的文件版本与 PR #1 历史快照不同而哈希不符，见下文 |
| 本分支完整 Python unittest discovery（首次整合） | 42 项运行，41 项通过；PyO3 binding 测试类初始化失败，不能记为整套通过 |

## 后续验收补充

### 必须执行的 MLIR 门槛

`test_mlir_resource_dispatch.py` 默认在普通开发环境缺少 MLIR 时会跳过相关测试；验收运行现在可设置 `SIM_ENGINE_REQUIRE_MLIR=1`。在此模式下，缺少基准证据、明确指定的插件目录、插件 `.so` 或 `mlir-opt` 都会导致失败，不会作为通过的 skip。新增 `.github/workflows/o5-mlir-integration.yml` 在干净 Ubuntu 24.04 runner 清理无关预装工具后下载并验证 LLVM 官方签名的 23.1.1 发行包，构建当前 checkout 的插件，再运行 Rust tests、PyO3 tests、六项 MLIR tests（明确要求零 skip）和完整 Python suite。job artifact 保存 Actions checkout SHA、PR head/base SHA、tree SHA、工具链版本、关键源码 SHA-256 和测试日志。该工作流须在 PR check 上成功后才满足 Linux 验收门槛。

首次 Linux 工作流尝试因下载并解压完整 LLVM 发行包耗尽 runner 磁盘空间，在任何测试步骤开始前由 GitHub runner 的 `No space left on device` 终止，不能算作代码测试失败或通过。第二次尝试改用官方签名仓库中固定版本 23.1.2 包后解决了磁盘问题，但仓库 CMake 对 23.1.1 使用 `EXACT` 约束，因而在插件编译前明确拒绝 23.1.2。随后几次尝试确认官方 Linux 23.1.1 发布包没有单体共享库和聚合 `MLIR` CMake 目标；C++ 插件可编译，但未链接运行库时 `mlir-opt` 无法加载它们。现 CMake 在单体共享库存在时按导入文件链接，在纯 Linux 静态组件包中让 Dialect 插件链接 `MLIRIR`，Pass 插件链接 `MLIRPass`，共用的 `LLVMSupport` 等由导入目标传递。当前版本在 macOS 标准共享库分支重建成功，必需 MLIR 测试 6/6 无 skip；新 Linux check 尚待验证静态组件插件是否能被工具正确加载，以及 PyO3、Rust 和完整 Python suite。

### 手算库存到达交互案例

新增 `test_supply_arrival_wakes_waiting_work_in_all_four_modes` 使用已有 B3 upstream-transport 小案例，分别验证 `legacy-minute-v1`/`event-time-v2` 与 MLIR 索引开/关的四种组合。Rust 四份完整 `RunResult` 除 profile 纳入的 `plan_fingerprint` 外完全一致，并逐一对照保存的 B3 oracle：短缺发生在 t=1、补给到达且备件消耗在 t=3、预防维修在 t=5 完成；资源指标与终态匹配 oracle。此新增测试在本机从当前 C++ 源码重建 `build-unix` 插件后，以 `SIM_ENGINE_REQUIRE_MLIR=1` 运行，6/6 通过、无 skip。

旧 B3 oracle 的整份 trace 有 15 条，而当前 Runtime trace 有 17 条；因此 oracle 对照使用原用例已承诺的完整资源业务指标、终态以及相关交互事件时间。四种新组合之间仍比较完整结果（仅忽略不同语义 profile 对应的 Plan fingerprint）。

### macOS PyO3 基线复现

在同一台 macOS 27 / Apple Clang 21 / rustc 1.90.0 / Python 3.12.13 主机，使用干净 worktree 与独立 virtualenv 从 `origin/main` `ae36799bb1238c430a830c26c6bf9db985db2ce2`（tree `877b1c852063ea7b86fe940bde2ae4f018bf81a1`）构建 PyO3 扩展。主线同样无法 import，dyld 报 `mis-aligned LINKEDIT string pool`（offset `0x001508F4`）；main 完整 unittest 为 31 项运行、绑定类初始化 1 项错误。整合分支在同一主机也有相同错误（offset `0x00150A34`）。这次对照复现说明错误在该 macOS/toolchain 主机上主线也存在；Linux PyO3 和全套测试仍须由上述 clean-runner check 通过。

`experiments/ir_validation/verify_manifest.py` 中的哈希是 PR #1 来源版本的历史快照校验，不会因整合时的新主线文件改动而自动更新。当前整合分支核验 302/311。为验证来源边界，在精确来源提交 `ed59f354df11d8855597e74099b75b5ea93acff1` 的干净 worktree 执行 `python3 experiments/ir_validation/verify_manifest.py`，得到 311/311、`passed: true`。对应重建命令为 `git worktree add --detach <dir> ed59f354df11d8855597e74099b75b5ea93acff1`，然后在 `<dir>` 内运行该脚本。当前整合分支 9 个哈希不匹配路径为 `.gitignore`、`README.md`、`benchmarks/hot_path/README.md`、`docs/architecture.md`、`docs/performance-optimization-plan.md`、`docs/roadmap.md`、`rust/runtime/src/plan.rs`、`rust/runtime/src/runtime.rs` 和 `src/sim_engine_compiler/ir/plan.py`。历史 manifest 与源报告保持原样；本次行为检查结果在本报告中独立记录。

PR #1 的三层 IR 验证报告使用合成模型以及固定 F35 oracle。其 `legacy_cases.py` 检查中的 3 项负例仍未被拒绝：负工作时长、未知装备组件引用、duration 单位字符串。已单独登记于 [严格输入校验后续项](STRICT_VALIDATION_GAPS.md)，PR #2 不改变输入接受或报错行为。

## 未执行项

本次没有重新跑性能基准，因此不将历史 O5 或 MLIR 报告中的数字当成这条整合分支的新性能结果。没有整合 cold-start/MC 分支、没有接入 O5d runtime，也没有执行分支归档或删除。上述限制与下一阶段安排应在 review 和后续分层 PR 中继续跟踪。
