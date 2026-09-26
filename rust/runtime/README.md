# Independent Rust runtime

阶段 C 的单样本与批量执行内核已经建立，并固定使用 Rust `1.90.0`。它直接读取
`aircraft-support-plan/v1alpha2`，不导入 Python，也不调用 `spare_mvp` 或
`AircraftSupportV1Model`。当前实现覆盖与 Python reference 相同的 B1/B2/B3
兼容范围；F35 43 天 seeds `0、1、7` 的完整采样请求、trace、指标和终态均已
跨语言差分通过。

当前模块：

```text
src/
  lib.rs            crate API
  main.rs           Plan 文件 → Result JSON 命令行入口
  batch.rs          共享 Plan、独立 RunState、Rayon 样本并行与稳定排序
  python.rs         PyO3 整批调用边界
  bin/stage_c_benchmark.rs  原生分段基准
  bin/observation_benchmark.rs  full/summary 交错执行基准
  bin/hot_path_profile.rs  phase 与分配热路径内部计数
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

`full` 为兼容默认值并保留完整 trace。`summary` 不构造 trace 事件 JSON，但继续执行相同
事件调度、RNG 请求、metrics 与终态构造；随机请求 tape 仍保留在结果中，供轨迹差分：

```bash
cargo run --release --manifest-path rust/runtime/Cargo.toml -- \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json \
  /tmp/f35-rust-seed-0-summary.json \
  --seed 0 --observation-level summary
```

批量执行保留输入顺序，重复 seed 由 `sample_index` 区分：

```bash
cargo run --release --manifest-path rust/runtime/Cargo.toml -- \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json \
  /tmp/f35-rust-batch.json \
  --seeds 7,0,7,1 --worker-threads 3
```

Rust 调用方可用 `PreparedBatchPlan::from_slice` 或 `from_plan` 建立已验证的
不可变句柄，并多次调用 `run_prepared_batch`。构建句柄时严格校验 Plan 和
可选资源索引，且只构建一次飞机故障槽、活动分组、组件子节点、phase 表和
资源反向索引；每个样本仍独立初始化 RNG、飞机、资源与作业状态。原有
`run_batch*`、CLI 和 Python 绑定入口内部也使用同一准备路径。缓存解码器
自身的校验与公开批量入口的校验可能仍各发生一次，这是固定加载成本，
不随样本数重复。

准备成本的诊断与 AMD128 批量前后对照位于
`benchmarks/batch_preparation/`。重复调用的热路径可运行
`prepared_batch_benchmark`，分别计入已准备句柄与公开批量入口的运行成本。

Python 绑定通过项目根目录的 Maturin 配置构建：

```bash
uv pip install --python .venv/bin/python -e .
.venv/bin/python - <<'PY'
from sim_engine_compiler import run_batch

result = run_batch(
    "tests/fixtures/synthetic/b1-execution-plan.json",
    [7, 0, 7, 1],
    worker_threads=3,
    observation_level="summary",
)
print([sample["sample_index"] for sample in result["samples"]])
PY
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

Python 绑定一次传入完整 Plan 与 seeds，一次返回完整 batch，没有逐事件 Python 回调。
F35 热路径报告见 `benchmarks/hot_path/README.md`。当前仍待阶段 C 后续处理的是 Plan
缓存失效合同和事件跳跃；后者必须证明不改变分钟 phase、随机调用和资源可见性语义。
