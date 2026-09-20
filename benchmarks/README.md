# Benchmarks

首个上游 oracle 已建立：[spare_mvp F35 43 天对照基线](spare_mvp_f35_43day/README.md)。它验证现有分钟、编译结构与 SimPy 调度路线，仍不表示本项目独立运行时或 Rust 加速已经实现。

独立 Rust runtime 的正式同 Plan 对比见[阶段 C 分段基准](stage_c/README.md)。该报告覆盖 Plan 读取/解析/指纹、RunState 初始化、单样本执行、批量执行、序列化、写盘和端到端路径，并同时保存 Python reference 与 Python 绑定数据。

每次报告保存环境、机器、代码/输入/Plan 指纹、profile、seed/样本编号、观测配置、规模、预热和重复次数，以及原始逐次数据。

分别测量 Adapter、冷编译、热缓存加载、RunState 初始化、单样本执行、批量执行、序列化、端到端墙钟时间与峰值内存。报告中位数及分布，明确进程、线程和样本数量；不将仪器化 trace 计时与 summary 计时直接混比。

比较对象包含旧分钟基线、上游已有编译结构路线（确认可运行后）、本项目 Python 参考与 Rust 内核。未取得精确输入的历史案例不列为本项目复现结果。

原始运行产物放 `runs/benchmarks/`；选定报告纳入版本管理时注明输入来源与生成命令，保留可复核数据，避免只保存结论。
