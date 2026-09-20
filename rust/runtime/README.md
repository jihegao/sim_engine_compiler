# Independent Rust runtime

阶段 C 的单样本执行内核已经建立，并固定使用 Rust `1.90.0`。它直接读取
`aircraft-support-plan/v1alpha2`，不导入 Python，也不调用 `spare_mvp` 或
`AircraftSupportV1Model`。当前实现覆盖与 Python reference 相同的 B1/B2/B3
兼容范围；F35 43 天 seeds `0、1、7` 的完整采样请求、trace、指标和终态均已
跨语言差分通过。

当前模块：

```text
src/
  lib.rs            crate API
  main.rs           Plan 文件 → Result JSON 命令行入口
  plan.rs           版本化加载、能力校验、跨语言稳定指纹
  rng.rs            CPython 整数种子 MT19937 与指数采样
  runtime.rs        独立数组状态、分钟 phase、资源事务与指标
```

执行固定计划：

```bash
cargo run --release --manifest-path rust/runtime/Cargo.toml -- \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json \
  /tmp/f35-rust-seed-0.json \
  --seed 0
```

跨语言验收：

```bash
.venv/bin/python -m unittest tests.differential.test_rust_runtime -v
```

`rust-toolchain.toml` 与 `Cargo.lock` 固定编译工具和依赖。Plan loader 对未知版本、
不支持的 semantic/work/RNG profile 及未实现能力显式失败。Plan 指纹使用与
Python `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`
一致的浮点与 JSON 编码；加载开启 `float_roundtrip`，避免高精度故障率在解析时
落到相邻的 IEEE-754 值。

Python 绑定、批量样本并行、事件跳跃和细分性能基准仍属于阶段 C 后续工作。
当前 CLI 是独立单样本后端，没有逐事件 Python 回调。

多个样本可共享只读 Plan，各自拥有 RunState。后续批量 API 仍需保证稳定结果顺序。
