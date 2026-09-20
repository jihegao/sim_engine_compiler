# Fixtures

当前包含 B1/B2/B3 synthetic 输入、序列化计划、reference 结果、固定旧模型 oracle，以及 F35 43 天 canonical 输入、完整计划和 seeds `0、1、7` 压缩 oracle。按来源分组：

- `synthetic/`：可手算、可重建的小模型，包含生成器或明确的人工构造步骤。
- `spare_mvp/`：允许纳入仓库的 canonical 输入及其导出来源。
- `golden/`：固定 profile 的旧模型 trace、账本、末态及随机请求 tape。

每组 manifest 记录来源类型、上游 revision/schema/Adapter、输入 hash、生成命令、语义 profile、seed/样本身份、horizon、预期结果与适用范围。synthetic 数据不能标为真实业务数据或历史 benchmark 复现。

本地数据库与未获准分享的数据不入 fixtures；本地临时数据放根目录 `data/local/`。测试运行产物放 `runs/`，不覆盖 golden。
