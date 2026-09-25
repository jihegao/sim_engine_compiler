# 三层 IR 与依赖派遣验收

2026-09-25 本轮实现 canonical → Business → symbolic Core → layout → Plan 的 Python/Rust 双语言主链。输入校验、持久化、重载、后端能力、来源映射及影响分析合同见[三层 IR](three-layer-ir.md)和[输入校验](strict-work-input-validation.md)。此前整合版本的性能快照单独保留在 [integrated](../benchmarks/integrated/results/macos-arm64-20260925/REPORT.md)，不与本轮性能相乘或合并。

## 候选实例派遣

`sim-engine-runtime plan.json result.json --dependency-dispatch` 显式开启新路径；批处理 `--seeds` 同样支持，Rust API 为 `run_batch_with_dispatch`。默认仍为原扫描路径，已有 Python canonical MC API 不自动启用本优化。

MLIR 索引 v2 包含本地容量、远端供应节点容量、库存和动态换件需求。运行期索引将静态活动/步骤映射到当前等待作业实例，资源变化、预约返还、运输到达和步骤转换使对应缓存失效并加入候选集合。候选按原优先级、开始时间、稳定 job ID 处理；阶段内只补入尚未访问的原有等待者，新建或已访问的作业延后到下一阶段，保持原快照可见性。作业存储追加、不复用槽位。

Full 模式必须在原顺序重放每分钟容量延迟事件，因此单列 `resource_dispatch_replay_visits`。真实候选访问与重放访问之和才是新路径的外层工作量。Summary 模式不需要生成这些事件，但业务状态、随机 tape 和结果仍完全一致。`queue_ns` 仅计队列构建/排序与阶段内失效合并，`queue_updates` 为等待作业失效通知次数；它们不是全部维护成本。未插桩端到端时间包含全部维护工作。

v1 索引继续支持旧缓存扫描；候选路径要求 v2。错误 schema/checksum/基础 Plan 指纹、缺失依赖、无效符号或后端缺口均报错，不自动回退。静态资源索引不改变 phase 顺序、RNG 身份或调用次数。

## 语义门槛与复现

`tests/differential/test_ir_layers.py` 验证五个 fixture × 两个 profile 的 Business/Core 跨语言全树一致、独立重载、规则修改和符号重定位。`test_dependency_dispatch.py` 比较无索引扫描、v2 缓存扫描和 v2 候选三个完整结果树：F35 seeds 0/1/7，minute/O5，Full/Summary；B1/B2/B3、运输边界、16 架容量竞争/缺货/远端运输及取消；批处理重复 seed 与线程顺序。还验证 Rust AOT 持久化 Core 经 MLIR 得到相同索引 Plan，以及重新计算 checksum 和候选数量后的缺失远端依赖仍被拒绝。

```bash
PYTHONPATH=src SIM_ENGINE_REQUIRE_MLIR=1 \
  SIM_ENGINE_MLIR_PLUGIN_DIR="$PWD/tools/mlir_dispatch/build-make" \
  SIM_ENGINE_MLIR_OPT=/opt/homebrew/opt/llvm/bin/mlir-opt \
  .venv/bin/python -m unittest tests.differential.test_ir_layers tests.differential.test_dependency_dispatch -v
PYTHONPATH=src .venv/bin/python benchmarks/dependency_dispatch/run_benchmark.py \
  --output benchmarks/dependency_dispatch/results/macos-arm64-20260925 \
  --plugin-dir tools/mlir_dispatch/build-make --mlir-opt /opt/homebrew/opt/llvm/bin/mlir-opt
PYTHONPATH=src .venv/bin/python benchmarks/dependency_dispatch/compile_cost.py \
  --output benchmarks/dependency_dispatch/results/compile-20260925
```

运行前需提交源代码、构建当前 checkout 的 LLVM/MLIR 23.1.1 插件并通过语义验收。基准先做精确结果校验，再独立运行未插桩计时；记录来源、二进制、输入和结果指纹。人工扩大的竞争案例明确标为 synthetic，不代表额外真实上游案例。运行期峰值 RSS 由独立 macOS `/usr/bin/time -l` 测量；分配次数和编译峰值内存未测，不作这些方面的收益声明。

本轮[完整证据与采用决定](../benchmarks/dependency_dispatch/results/macos-arm64-20260925/REPORT.md)显示：F35 minute 访问量下降，但 O5 与集中竞争未获稳定端到端收益；维持显式 opt-in，不设为默认。新编译链物化与校验有额外成本，已单独测量。粗粒度 phase operation 的保守读写集合不用于阶段重排；不声称通用 IR VM、持久事件回调执行、Agent patch 服务或运行中迁移已实现。
