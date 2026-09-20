# Rust runtime — reserved for phase C

当前未建立 crate、Cargo workspace 或 Python 扩展。阶段 B 先冻结可运行 Plan 与参考执行语义，阶段 C 再建立实际工程和锁定工具链。

计划模块：

```text
src/
  lib.rs            批量执行入口
  plan.rs           版本化加载与能力校验
  event_queue.rs    确定性二叉堆
  state.rs          每样本独立的数组状态
  operations.rs     指令分派与后端能力
  resources.rs      容量/库存/预约/在途事务
  rng.rs            兼容算法与随机请求回放
  metrics.rs        区间积分与观测输出
  batch.rs          样本并行与稳定结果顺序
```

Python 绑定建议独立放在未来的 `rust/python/` crate，使内核可独立验证。绑定方式在 C 阶段决定，初期不引入逐事件 Python 回调。

多个样本共享只读 Plan，各自拥有 RunState。能力不完整时拒绝 Plan；不按飞机领域字符串写特例。跨语言测试使用固定计划、随机 tape、资源账本和首处分歧输出。
