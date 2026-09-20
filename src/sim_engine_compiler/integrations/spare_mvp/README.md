# spare_mvp integration

唯一接入边界：上游正式 Adapter 已生成的 canonical `simulation_inputs`。当前没有可用输入样例或上游 checkout，因此接口签名尚未核验。

阶段 A 先确认上游 `ProjectJsonExporter / SimulationAdapter / contracts` 的实际路径、版本与调用方式，以及 `SimulationTask → EngineRunner → SimulationEngine` 是否已实现及其协议。讨论中的名称不能直接当作可调用 API。

阶段 B 计划增加：

- `importer.py`：验证 canonical 合同，调用领域构建器，生成 Business IR，记录原始输入身份、默认值及 source map。
- `engine.py`：在上游协议确认后适配编译/运行/取消/结果边界，隔离可选上游依赖。
- `results.py`：指标与 trace 映射，保留缺失/不支持状态，不伪造兼容结果。

生产包不导入 legacy AircraftSupportV1Model。差分工具在隔离环境中运行旧模型，使用文件交换输入、随机 tape 和 trace。不要从本地数据库取代 canonical 合同，也不假定 Project 与 IR 能双向无损同步。
