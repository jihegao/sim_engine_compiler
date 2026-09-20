# Python reference runtime

阶段 B 实现。执行与 Rust 相同的 Plan 语义；不通过旧模型实例、继承或动态调用来执行。旧模型只作为差分 oracle。

计划模块：`runtime.py`、`event_queue.py`、`state.py`、`operations.py`、`resources.py`、`rng.py`、`observations.py`。先用可读实现保证确定性和可解释性，再以测量支持优化。

核心行为：只读计划与每样本可变状态分离；事件键显式排序；timer version 与 generation 检查；资源事务一次结算；状态改变通知等待者；时间条件触发独立定时事件；采样请求可回放并校验身份。

结果记录结束原因和未完成工作。观测模式不得改变抽样和业务状态。所有能力均待实现，当前没有 `run()` 入口。
