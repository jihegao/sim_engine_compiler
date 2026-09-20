# Compiler

目标入口草案：`compile_model(model_revision, target_capabilities, options) -> CompilationResult`。不是已发布 API；`CompilationResult` 需区分成功计划与错误诊断，不以半成品 Plan 假装成功。

按需要建立 `pipeline.py`、`passes/`、`operations.py`、`diagnostics.py`、`cache.py`。passes 顺序为验证 → 符号/类型/单位 → 领域 lowering → 图与操作检查 → 依赖分析 → 布局/专门化 → 打包验证。

领域插件由调用方显式注册；编译器不导入 spare_mvp，也不硬编码飞机语义。每个 pass 返回来源映射和诊断，并声明保持的不变量。依赖分析同时覆盖数据写入与时间条件。

静态结构缓存和运行身份分离；缓存键须纳入所有影响布局或生成指令的参数、版本与选项。首版使用完整正确的重编译，阶段 D 再加入经过验证的增量失效。
