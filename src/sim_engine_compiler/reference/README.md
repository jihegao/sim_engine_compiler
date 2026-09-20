# Python reference runtime

已实现 B1/B2/B3 的独立 Plan 解释器。它不通过旧模型实例、继承或动态调用执行；旧模型只由仓库根目录的隔离 oracle 脚本运行。

计划模块：`runtime.py`、`event_queue.py`、`state.py`、`operations.py`、`resources.py`、`rng.py`、`observations.py`。先用可读实现保证确定性和可解释性，再以测量支持优化。

已实现只读计划与每样本状态分离、显式分钟 phase、稳定串行任务、容量/库存/预约/运输账本、飞行暴露故障时钟、预防维修、随机请求 tape 与业务 source map。当前执行器仍按分钟推进，用于可读语义基线。

结果记录结束原因、trace、核心指标及完整终态。入口是 `SimpyReferenceRuntime.run()`，文件 CLI 为 `scripts/run_reference_plan.py`。
