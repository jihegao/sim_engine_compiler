# Differential

阶段 A/B 建立旧模型与 Python 的比较，阶段 C 已加入独立 Rust runtime。
`test_rust_runtime.py` 会构建固定工具链的 release crate：四个 B1/B2/B3 合成
Plan 与完整保存结果比较，F35 seeds `0、1、7` 则在测试时从同一份序列化 Plan
分别生成 Python 与 Rust 完整结果并逐字段比较。

观测隔离同时覆盖四个 synthetic Plan、F35 seeds `0、1、7`、截断 horizon 和
`[7,0,7,1]` 批量请求。批量路径分别以 1/3 线程执行 `full/summary`，核对输入顺序、
重复 seed、全部非 trace 字段，并要求 summary trace 为空。Python binding 用例覆盖相同的
截断与批量边界；native extension 未安装时用例显式失败，验收前须重新构建绑定。

比较前先核对 canonical 输入、语义 profile、参数、初始状态、horizon、样本身份和随机请求 tape。对齐业务事件、时间/phase、资源账本与末态，输出首处分歧及其源规则/字段。

随机请求身份不匹配立即停止，不跳过 tape 项目。旧模型重复等待事件如需规范化，先明确合同和保留信息，不可为了通过而丢弃有业务意义的事件。

差分工具可在独立环境调用 legacy 模型；生产编译器与参考运行时不能依赖它。schema 验证或最终均值接近不等于语义兼容。
