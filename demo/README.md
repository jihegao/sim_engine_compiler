# 本地交互验证入口

此页面在 `127.0.0.1` 上运行，使用仓库中固定的 B1、B3、F35 canonical
`simulation_inputs`。它调用现有 AOT/MLIR 编译入口和 Rust runtime CLI；不读取
Project JSON，不另写业务计算。页面不提供远程服务或持久化数据库。

## 启动

需要 Python 3.12、SimPy 4.1.1 和 Rust 工具链。先构建两个 release CLI：

```bash
cargo build --release --locked --manifest-path rust/compiler/Cargo.toml --bin sim-engine-compiler-aot
cargo build --release --locked --manifest-path rust/runtime/Cargo.toml --bin sim-engine-runtime
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python simpy==4.1.1
.venv/bin/python demo/validation_app.py --port 8765
```

浏览器打开 `http://127.0.0.1:8765/`。需要 MLIR 索引时，先按
[`docs/mlir-resource-dispatch-pilot.md`](../docs/mlir-resource-dispatch-pilot.md)
构建固定 LLVM/MLIR 23.1.1 插件，再设置：

```bash
export SIM_ENGINE_MLIR_PLUGIN_DIR=/absolute/path/to/tools/mlir_dispatch/build-unix
export SIM_ENGINE_MLIR_OPT=/absolute/path/to/llvm-23.1.1/bin/mlir-opt
```

页面对每组使用同一 canonical 输入、seed 列表、`legacy-sequential-v1` RNG、
`stable-topological-serial` 工作策略与 `full` 观测。分钟推进始终作为基线；
O5 和 MLIR 索引分别以独立计划运行。AOT Plan 缓存只用于无 MLIR 索引的
组合，展示同一模型的首次生成与命中。当前接口不支持把 MLIR 派生索引写入
AOT 二进制缓存，因此页面会明确拒绝同时开启两个开关。

完整结果按样本逐字段比较，只忽略不同时间 profile 应有的 Plan 指纹差异；
首次分歧显示事件、状态或指标路径，以及可用的规则与来源位置。页面提供
本次 JSON 报告下载，记录输入指纹、合同、二进制 SHA-256、源码 checkout
提交与计划指纹。下载由浏览器执行，不会自动写入仓库。

编译与批量运行的耗时为进程墙钟；Rust CLI 的只读 profile 输出记录首个
seed 的计划加载、初始化、执行时间及资源派遣计数。这些值只用于交互诊断。
一次运行的速度比值不构成正式性能结论；正式基准仍须固定构建、顺序、热身、
重复次数和原始记录，并先通过语义验收。
