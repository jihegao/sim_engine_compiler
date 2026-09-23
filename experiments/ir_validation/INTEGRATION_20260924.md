# O5 与三层 IR 验证整合记录

日期：2026-09-24

集成分支：`codex/o5-mlir-integration-20260924`

基线：`main` / `origin/main` `ae36799bb1238c430a830c26c6bf9db985db2ce2`

吸收来源：`codex/event-time-v2-o5` `ed59f354df11d8855597e74099b75b5ea93acff1`，其中 PR #1 已合并的三层 IR 验证提交随该分支一并吸收。

## 范围与结论

本次从最新 `main` 整合 O5a 保守跳时和 PR #1 三层 IR 验证，保留 `main` 已有的 MLIR 资源派遣试点。没有整合 MC 接口、Rust AOT/缓存、四项业务语义修复，也没有把 O5d guarded continuous advance 实验候选接入运行时。原有 O5/O5d 报告、计时数据、来源清单与实验差异均保留；本文件只记录本次整合验证。

MLIR pass 现在接受 `legacy-minute-v1` 和 `event-time-v2`，并要求模块携带完全匹配的 canonical 15-phase 顺序。MLIR 编译入口新增 `--semantic-profile`，默认为旧 profile。新的组合回归对 F35 canonical 输入在索引开/关两条路径运行 Rust，并对 seeds `0、1、7` 比较完整 `RunResult`；三组均逐字段完全一致，索引的基础 Plan 身份也与未索引 Plan 相同。

这证明 O5 与 MLIR 索引在当前 F35 输入上的组合语义一致，不代表新的端到端性能结果，也不扩展至其他业务 profile 或输入。

## 验证结果

| 检查 | 结果 |
|---|---|
| Rust runtime `cargo test --locked --manifest-path rust/runtime/Cargo.toml` | 29 项通过：14 library、6 continuous-advance experiment、6 event-time benchmark、3 profile tests |
| `tests/differential/test_event_time_runtime.py` | 9/9 通过；包含旧语义、唤醒边界、F35 seeds 和 event-time profile 约束 |
| `tests/conformance/test_b1_reference.py` | 13/13 通过 |
| `tests/differential/test_mlir_resource_dispatch.py` | 5/5 通过；含 O5 与 MLIR 索引开/关的三 seed 完整结果对比 |
| PR #1 三层 IR `run_cases.py` | 37/37 案例通过；Python reference、indexed Python 与 Rust 后端结果均执行 |
| PR #1 `test_review_fixes.py` | 9/9 通过 |
| PR #1 adversarial validation | 固定生成器生成 100 个模型，0 个差异；15/15 拒绝探针通过 |
| PR #1 legacy F35 检查 | 12/12 正例和 64/64 显式断言通过；保存的旧模型 oracle 对 seeds `0、1、7` 均无差异 |
| MLIR pass build | `cmake --build tools/mlir_dispatch/build-unix --parallel 2` 成功 |
| 旧来源 manifest | `verify_manifest.py` 核验 302/311；9 个条目因整合分支上的文件版本与 PR #1 历史快照不同而哈希不符，见下文 |
| 完整 Python unittest discovery | 42 项运行，41 项通过；PyO3 binding 测试类初始化失败，不能记为整套通过 |

完整 Python suite 的唯一阻塞是本机生成的 `src/sim_engine_compiler/_runtime.abi3.so` 被 macOS dyld 拒绝加载：`mis-aligned LINKEDIT string pool, fileOffset=0x00150A34`。已分别尝试 editable `uv pip install` 和 `.venv/bin/maturin develop --release --locked`；两种构建路径均得到相同加载错误。Rust 内核及 Python reference/Rust CLI 测试照常运行。PyO3 Python 调用边界在本机仍未验证，需在合适的 Apple linker/toolchain 环境修复后重跑 `tests/differential/test_python_binding.py` 和完整 suite。

`experiments/ir_validation/verify_manifest.py` 中的哈希是 PR #1 来源版本的历史快照校验，不会因整合时的新主线文件改动而自动更新。9 个不匹配路径为 `.gitignore`、`README.md`、`benchmarks/hot_path/README.md`、`docs/architecture.md`、`docs/performance-optimization-plan.md`、`docs/roadmap.md`、`rust/runtime/src/plan.rs`、`rust/runtime/src/runtime.rs` 和 `src/sim_engine_compiler/ir/plan.py`。历史 manifest 与源报告保持原样；本次行为检查结果在本报告中独立记录。

PR #1 的三层 IR 验证报告使用合成模型以及固定 F35 oracle。其 `legacy_cases.py` 检查中的 3 项负例仍未被拒绝：负工作时长、未知装备组件引用、duration 单位字符串。正例与现有 oracle 比较通过不能掩盖这三项生产兼容编译器校验缺口。

## 未执行项

本次没有重新跑性能基准，因此不将历史 O5 或 MLIR 报告中的数字当成这条整合分支的新性能结果。没有整合 cold-start/MC 分支、没有接入 O5d runtime，也没有执行分支归档或删除。上述限制与下一阶段安排应在 review 和后续分层 PR 中继续跟踪。
