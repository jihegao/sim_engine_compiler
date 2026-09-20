# ADR 0001：三层 IR 与可替换执行器

- 日期：2026-09-20
- 状态：采用为项目初始架构；细节合同在阶段 A/B 冻结
- 来源：[设计讨论](chatgpt-conversation://6aaf8dfc-02e0-83ea-8eb1-460c5abf7b5f)

## 决策

采用 Business IR → Core Simulation IR → Execution Plan。Python 拥有编译和独立参考执行，Rust 拥有性能内核。首个领域包为 aircraft_support；通过 canonical simulation_inputs 对接 spare_mvp。

采用结构与指令计划编译：领域变化重新生成计划，运行时二进制保持稳定。仅在性能证据支持时考虑原生代码专门化。原型保持 Project 真源；IR-native 创作模式后续显式引入。

## 理由

业务语义需要可编辑、可追溯；执行器需要紧凑、已验证的数据。把两者混在一份数组清单里会损失规则表达，把旧 Python 对象模板当成独立 IR 则继续耦合旧模型。三层表示将领域验证、通用操作语义与运行布局分开。

## 后果

需要维护版本、操作能力表、source map 和差分工具。必须先冻结同时事件、随机与资源语义，才能判断后端替换是否等价。Python 参考执行器不能继承旧模型来掩盖实现缺口。

## 暂不采用

逐行将 Mesa 模型翻译成 Rust；预展开全部随机分支；原型即引入 LLVM/MLIR；每次 agent 修改重建本地二进制；以 SimPy generator 作为业务模型真源；单个世界内部并行事件；运行中热改模型。这些不妨碍后续以独立 ADR 评估扩展。
