# Benchmarks

Schelling source candidate 的 51×51 Rust `current` 读视图优化边界与同 Plan 交替测量见 [ABM source scale check](abm_source_scale/README.md)。这是单输入端到端运行时测量，未完成 NetLogo source-gold 或各阶段正式性能验收。

首个上游 oracle 已建立：[spare_mvp F35 43 天对照基线](spare_mvp_f35_43day/README.md)。它验证现有分钟、编译结构与 SimPy 调度路线，仍不表示本项目独立运行时或 Rust 加速已经实现。

独立 Rust runtime 的正式同 Plan 对比见[阶段 C 分段基准](stage_c/README.md)。该报告覆盖 Plan 读取/解析/指纹、RunState 初始化、单样本执行、批量执行、序列化、写盘和端到端路径，并同时保存 Python reference 与 Python 绑定数据。

观测级别隔离与执行热路径证据见 [F35 执行热路径与观测隔离](hot_path/README.md)。该报告
分开保存未插桩交错墙钟、内部 phase/计数器和系统采样火焰图；结果表明 trace JSON
不是当前主要执行瓶颈，逐分钟任务扫描、Plan spec 克隆和树 Map 状态操作才是下一轮重点。

Project export/Adapter profile、Rust AOT Plan compiler 与 pre-Adapter Project 指纹缓存实验见
[spare_mvp 冷启动实验](cold_start/README.md)。该报告把第一次启动和重复模型缓存命中分开，
并明确 Rust Project Adapter 尚未实现。

每次报告保存环境、机器、代码/输入/Plan 指纹、profile、seed/样本编号、观测配置、规模、预热和重复次数，以及原始逐次数据。

分别测量 Adapter、冷编译、热缓存加载、RunState 初始化、单样本执行、批量执行、序列化、端到端墙钟时间与峰值内存。报告中位数及分布，明确进程、线程和样本数量；不将仪器化 trace 计时与 summary 计时直接混比。

比较对象包含旧分钟基线、上游已有编译结构路线（确认可运行后）、本项目 Python 参考与 Rust 内核。未取得精确输入的历史案例不列为本项目复现结果。

原始运行产物放 `runs/benchmarks/`；选定报告纳入版本管理时注明输入来源与生成命令，保留可复核数据，避免只保存结论。
