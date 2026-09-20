# spare_mvp integration

唯一接入边界：上游正式 Adapter 已生成的 canonical `simulation_inputs`。当前已使用固定 AMD128 提交和只读数据库导出 F35 fixture，并记录 schema、Adapter、输入 hash 与来源 manifest。

导出工具为仓库根目录 `scripts/export_spare_mvp_fixture.py`，只调用 `ProjectJsonExporter / SimulationAdapter / contracts`。执行时需要显式上游 checkout 和数据库路径；生产 runtime 不导入这些依赖。`SimulationTask → EngineRunner → SimulationEngine` 的产品集成协议仍待核验。

后续集成计划：

- `importer.py`：验证 canonical 合同，调用领域构建器，生成 Business IR，记录原始输入身份、默认值及 source map。
- `engine.py`：在上游协议确认后适配编译/运行/取消/结果边界，隔离可选上游依赖。
- `results.py`：指标与 trace 映射，保留缺失/不支持状态，不伪造兼容结果。

生产包不导入 legacy AircraftSupportV1Model。差分工具已在隔离环境中运行旧模型，使用文件交换输入、随机请求、trace 和终态；F35 seeds `0、1、7` 的固定 oracle 已纳入 fixtures。不要从本地数据库取代 canonical 合同，也不假定 Project 与 IR 能双向无损同步。
