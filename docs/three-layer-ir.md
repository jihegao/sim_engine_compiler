# 真实兼容链中的三层 IR

Python canonical 编译入口和 Rust AOT 现在经过同一组版本化边界：

`canonical simulation_inputs → BusinessIR → CoreIR → layout → ExecutionPlan`

Business 的 `sections` 保存业务实体、任务模板、活动、组件分布和策略，实体附有稳定 `business_id` 与原始 `source_path`。它不含展开后的任务波次，也不含 Plan 索引。未知 Project JSON 仍被拒绝；唯一输入来源仍是上游 Adapter 的 canonical 合同。保存的 Business 产物拥有全部后续 lowering 输入，不持有隐藏的原输入对象。

领域 lowering 位于 `domains/aircraft_support/lowering.py` 与 Rust `aircraft_support.rs`。已有兼容 helper 产生临时类型化记录，Core 构建器将引用变为稳定符号；该阶段不创建最终 ExecutionPlan。Core 中任务模板已展开为任务实例，组件分布已转换为兼容故障率，资源/维修/作业前驱均以符号引用表示。它带有步骤级资源、运输、动态状态和唤醒依赖，以及版本化 phase operation 合同。保存的 Core 可以独立编辑参数并再次编译，不需要 Business 或 canonical 文件。

Core phase operations 是已有飞机兼容规则的粗粒度版本化操作，保守声明全部可能状态读写和 RNG 副作用；不据此移动、融合或并行执行阶段。步骤级资源依赖提供精确的 MLIR guard 分析边界。此里程碑不声称实现了完整跨领域指令集、Agent patch API 或通用物理求解器。未知 operation、删除依赖、backend 缺口、未知引用、无效字段类型及错误版本/校验和在 Plan 输出前报错。

`compiler/layout.py` 和 Rust `layers::compile_core` 从 Core 的有序符号表分配稠密地址，保留源映射、阶段顺序和 RNG 的稳定业务身份。可执行属性类型合同保存在 `ir/attribute_types.json`，操作合同保存在 `ir/compatibility_operations.json`；两种语言使用同一份声明，独立校验和执行。Plan 仍是既有 v1alpha2 语义格式，合法原输入的 Plan 全树和指纹保持不变。AOT 编译版本升至 v1alpha5，旧编译缓存不冒充本链产物。

每层 envelope 包含 `version/payload/fingerprint`；Core 记录来源 Business 指纹、当前 canonical 派生摘要与原始 canonical 摘要。Plan 自带源输入摘要；产物 bundle 的 `lineage.json` 关联 Business/Core/Plan 指纹及符号到 Plan 的位置。`revision_impact` 将规则修改定位到受影响的 Core 实体/步骤、原始字段路径及新旧 Plan 地址。只有提供同一 bundle 的 lineage，才能声称某 Plan 对应某个 Business/Core 修订。

## 重载和复现

```bash
PYTHONPATH=src .venv/bin/python scripts/compile_ir.py \
  tests/fixtures/synthetic/b1-daily-operations.json /tmp/b1-plan.json \
  --artifacts-dir /tmp/b1-ir
PYTHONPATH=src .venv/bin/python scripts/compile_ir.py /tmp/b1-ir/core.json /tmp/reloaded-plan.json
cargo build --locked --release --manifest-path rust/compiler/Cargo.toml
rust/compiler/target/release/sim_ir_compiler /tmp/b1-ir/business.json /tmp/rust-core.json --output-kind core
rust/compiler/target/release/sim_ir_compiler /tmp/rust-core.json /tmp/rust-plan.json
```

两个工具都支持 `--output-kind business|core|plan`。Core 无法逆向重建原始 Business 模板，逆向请求会被拒绝。既有 Python API 与 Rust canonical MC API 保持调用兼容。

MLIR 工具 `scripts/compile_mlir_execution_plan.py` 可直接接受保存的 Core 或 Business；其投影从 Core 符号表和布局获得步骤/资源地址，随后运行 pass，最后才创建最终 Plan。base-plan fingerprint 从同一布局字典计算，不能从旧 Plan 反推并伪称 Core 来源。索引开/关、完整性和后端校验继续保留。

`tests/differential/test_ir_layers.py` 验证五个 fixture × 两个 profile 的跨语言 Business/Core 全树一致、两种语言从持久化中间层恢复原 Plan、规则修改对实际 trace 的影响、符号重定位、重新计算校验和后的非法操作/类型/引用/依赖拒绝。真实 F35 的故障、备用机派遣、库存与资源竞争仍由已有 oracle/完整结果差分验收，不由格式测试替代。

## PR #8 复审后的身份与追溯合同

Core 升为 `simulation-core-ir/v2`，每个表行持久保存 `source_path` 元数据。该路径在 lowering 时捕获，重排 Core 行只改变布局地址；`lineage` 不再从当前行号推算原始数组位置。由 fleet_count 生成、没有显式 asset 的飞机记录来源为 `aircraft.fleet_count`，不虚构不存在的原始记录。

预防周期符号是稳定飞机 ID、活动 ID 与 `cycle_key` 的规范 JSON SHA-256，带 `preventive-cycle:` 前缀。优先采用非空字符串 `id`/`cycle_id`（同时提供时须一致）；没有显式周期 ID 时，以 `equipment_id` 作为同一飞机/活动内的自然键。阈值与初始寿命不进入身份。相同 owner/activity/key 的重复周期会被明确拒绝，需要显式周期 ID 消除歧义；数组下标和 source_path 不参与身份。Core 校验会重新计算符号并检查引用，不能只改 owner/key 而保留旧符号。

`compiler-lineage/v2` 保存符号、原始路径及当前 Plan 地址；`compiler-impact/v2` 用 `kind=contract/entity/layout/provenance` 区分合同、实体、布局和来源变化。合同项带 `field/core_path/before/after`，可直接定位 Core 合同字段；不为编译选项猜测不存在的 canonical 来源路径。实体和布局项保留原始字段定位及新旧 Plan 地址；相同内容的表行或步骤移动也会报告布局变化。

旧 Core v1 缺少可靠身份与来源信息，不能无损猜测迁移，当前加载器拒绝它；应从保存的 Business v1 或 canonical 重新 lowering 到 v2。旧 Core 上的独立编辑须显式重放到新产物，不自动静默丢弃。历史基准产物保留原版本。合法固定输入生成的 Execution Plan 全树与指纹保持不变，AOT 缓存版本更新用于拒绝旧编译器产物。复审修复范围及回归命令见[复审记录](pr8-review-fixes.md)。
