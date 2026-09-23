# MLIR 资源依赖索引试点

状态：2026-09-24 已完成 F35 真实案例的编译、Execution Plan 输出、Rust 消费、差分和三组成本对照。LLVM/MLIR 固定为 23.1.1。完整原始证据与生成计划见 [`f35-20260924-v1`](../benchmarks/mlir_resource_dispatch/results/f35-20260924-v1/README.md)。

## 试点边界

输入仍由 `integrations/spare_mvp` 的 canonical `simulation_inputs` 入口处理；MLIR 工具不读取 Project JSON，也不实现第二套业务解释器。现有 Python 编译器在内存中归一化活动、工作步骤、组件和供应路线，随后把资源派遣相关的 Core 语义投影为 `sim.activity`、`sim.work_step`、`sim.component` 和 `sim.supply_route` 属性记录。MLIR pass 校验 profile、完整读集合/副作用、稳定身份、source path 和静态依赖，然后生成资源键到候选步骤的确定性反向索引。最终导出的 Execution Plan 携带该可选索引；优化前的临时 plan 不单独导出。

这是 Core IR 的一个有限投影，不是完整 Business/Core IR 物化。当前 F35 plan 提供人员/设备数量、节点、静态备件和动态 LRU 换件需求；它没有设备型号兼容、运行时日历 guard 或可变优先级规则，因此首轮索引不表示这些语义。未来增加读状态必须扩展并验证 `sim` 合同；pass 不认识的操作、属性、读集合或副作用会报错。

计划扩展带独立 checksum 和基础 plan fingerprint。基础语义 fingerprint 排除派生索引，因此三组计划保持同一 fingerprint。Rust 加载时会校验扩展版本、MLIR 版本、pass 名、checksum、stable IDs、资源引用，以及从 plan 重新推导出的依赖完整性；不完整或陈旧索引明确失败。无索引的旧计划仍走原有的全量动态检查。

Rust 执行器仍遍历全部等待作业，并保持原有优先级、开始时间和 job ID 顺序。它缓存作业当前步骤的阻塞原因；人员/设备预约与释放、本地库存消费/返还/到达、供应路线源库存变化，以及作业自身预约变化会使受影响缓存失效。其余等待者复用相同动态检查结果；每分钟容量延迟事件仍在原排序位置重放。未改写时间、事件阶段、随机抽样或资源竞争顺序。

## 验收和结果

基准输入是固定的 43 天 F35 canonical 案例，来源 `spare_mvp` revision `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`，canonical `source_inputs_sha256` 为 `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`，语义 plan fingerprint 为 `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`。

三个对照共执行 seeds `0、1、7`，各重复三次，使用同一 release Rust runtime 和 full observation：

| 对照 | 中位编译耗时 | 等待作业候选访问 | 动态 guard 重检 | 缓存命中 | 中位端到端运行耗时 | 编译+加载+九次运行总成本 |
|---|---:|---:|---:|---:|---:|---:|
| 现有编译链 | 0.0563 s | 1,005,081 | 1,005,081 | 0 | 204.954 ms | 1.9255 s |
| MLIR 校验、业务 pass 关闭 | 0.1202 s | 1,005,081 | 1,005,081 | 0 | 206.407 ms | 1.9852 s |
| MLIR 资源索引 pass 开启 | 0.1474 s | 1,005,081 | 42,936 | 962,145 | 185.868 ms | 1.8435 s |

三个对照的完整 `RunResult` JSON 树逐字段完全一致，覆盖 trace、采样请求、metrics 和 terminal state。索引 pass 生成 852 条候选规则。对该 F35 工作负载，完整 guard 重检减少 95.73%；等待作业外层访问次数没有减少。九次运行加一次计划加载后，MLIR 开启组的总成本比现有编译链低 0.0820 秒，即 4.26%。编译、加载和每次运行的 raw records、fingerprint、checksum 及两个 `sim` MLIR 投影见同目录 `evidence.json`、`compile-report.json`、`benchmark.json` 和 `mlir_*_core.mlir`。

这个总成本结果针对 9 次执行。按编译/加载差额与逐样本中位耗时估算，约运行 6 个样本达到 break-even；该值是本机 F35 的粗略估计。硬件、输入稀疏度和重复运行数会改变结论。MLIR 工具链安装、C++ 插件构建及 Rust 二进制构建不计入表中；这些一次性开发/部署成本单独处理。

该仓库先前没有同算法的手写反向依赖索引，因此本次没有把它与旧手写索引实现混为一谈。实际收益来自“MLIR pass 生成索引 + Rust 执行器使用索引”的组合，不能解读成 MLIR 本身带来的 95.73% 加速。后续若评估 MLIR 相对直接 Python/Rust 索引生成的维护和编译收益，应增加同算法手写生成器对照。

## 重跑

需要 Python 3.12、Rust 1.90、CMake、Make，以及 LLVM/MLIR 23.1.1。设置 `MLIR_PREFIX` 指向包含 `bin/mlir-opt` 与 `lib/cmake/{llvm,mlir}` 的安装前缀，然后执行：

```bash
python3.12 scripts/benchmark_mlir_resource_dispatch.py \
  benchmarks/mlir_resource_dispatch/results/f35-20260924-v1 \
  --repeats 3 --compile-repeats 3
```

脚本会构建 MLIR 插件和 Rust benchmark，生成三份计划、编译 timing、逐样本 profile、exact-result parity 结果及摘要。它不运行 JIT、LLVM 代码生成或 GPU 后端。
