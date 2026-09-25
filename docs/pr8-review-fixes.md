# PR #8 复审修复（2026-09-26）

针对 `c3fe646` 的 1 项 P1、3 项 P2，先加入失败回归，再修复。原有 CI 成功不能替代这些新增边界；合并门槛为修复提交的完整 Linux CI、必需 MLIR 零跳过及四项回归全部通过。

| 问题 | 修复 | 可执行回归 |
|---|---|---|
| 共享远端池释放漏唤醒 | 人员、设备分别按实际供应节点失效；释放 trace 保留原合同 | 两个目的节点，人员池/设备池/两类不同池，minute/O5 × Full/Summary × 6 个截止点，三个结果树精确比较，且两架飞机预防维修均完成 |
| 修订影响漏报 | 区分 contract、entity、layout、provenance；比较行和步骤的地址，即使内容相等 | 仿真时长、时间 profile 单独变化；飞机重排；周期插入/重排及参数编辑 |
| 周期身份依赖位置 | 飞机 ID + 活动 ID + 显式周期 ID 或设备自然键；不含数组路径或阈值 | 飞机和周期插入/重排后原符号与 owner 一致；阈值修改不改身份；歧义重复和符号/owner/key 不一致被拒绝；Python/Rust 中间层一致 |
| 飞机来源指向当前行号 | Core 表行持久保存 lowering 捕获的原始路径，lineage 只更新 Plan 地址 | Core 重排并序列化重载、Business 重排；F35-02 始终指向它自己的输入记录；生成飞机不虚构 asset 下标 |

P1 在修复前已实际执行复现：供应池释放后，扫描路径的另一目的节点作业已开始，候选路径仍停在 waiting。修复后共 72 组 profile/观测/截止点组合通过三个完整结果树对比，另断言完成事件覆盖两架飞机。比较包含 trace、随机请求、metrics、终态和账本，不仅比较均值。

Core/lineage/impact 更新为 v2，AOT 编译版本为 v1alpha5。Plan 合同未改，五个固定输入与两个 profile 的现有 Plan/跨语言/旧模型 oracle 回归保留。旧 Core v1 的迁移边界及身份歧义处理见[三层 IR 合同](three-layer-ir.md)。

```bash
cargo test --locked --manifest-path rust/runtime/Cargo.toml
cargo test --locked --manifest-path rust/compiler/Cargo.toml
PYTHONPATH=src SIM_ENGINE_REQUIRE_MLIR=1 \
  SIM_ENGINE_MLIR_PLUGIN_DIR="$PWD/tools/mlir_dispatch/build-make" \
  SIM_ENGINE_MLIR_OPT=/opt/homebrew/opt/llvm/bin/mlir-opt \
  .venv/bin/python -m unittest tests.differential.test_dependency_dispatch tests.differential.test_ir_layers -v
```

完整 Linux CI 使用固定 LLVM/MLIR 23.1.1，从当前 checkout 构建插件和 Python 扩展，执行两套 Rust 测试、Python 绑定、必需 MLIR 和 Python 全套；运行日志、PR head/tree/toolchain 指纹在 PR 检查附件。本机 macOS 的既有 PyO3 LINKEDIT 加载错误仍单独记录，不将本机绑定无法运行写成全套通过。

本轮未重测性能，历史基准仍绑定其原始提交；候选派遣保持显式实验开关，不因正确性修复而自动提升默认采用状态。
