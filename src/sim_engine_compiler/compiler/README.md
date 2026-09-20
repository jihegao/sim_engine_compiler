# Compiler

入口为 `compile_aircraft_support(canonical_inputs) -> ExecutionPlan`，并可通过 `scripts/compile_execution_plan.py` 写成 JSON。它仍是 alpha 合同；后续将返回带诊断的 CompilationResult。

按需要建立 `pipeline.py`、`passes/`、`operations.py`、`diagnostics.py`、`cache.py`。passes 顺序为验证 → 符号/类型/单位 → 领域 lowering → 图与操作检查 → 依赖分析 → 布局/专门化 → 打包验证。

编译器不导入 spare_mvp；canonical Adapter 只在隔离导出脚本中使用。当前 aircraft-support lowering 尚在专用模块中，后续提取领域插件协议。Plan 已包含任务、活动、组件/故障树、预防周期、资源/库存和预编译供应路线，并保留 source path、输入指纹及 profile。

静态结构缓存和运行身份分离；缓存键须纳入所有影响布局或生成指令的参数、版本与选项。首版使用完整正确的重编译，阶段 D 再加入经过验证的增量失效。
