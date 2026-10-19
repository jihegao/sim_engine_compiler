# K02 已验收目录归档交付（2026-10-19）

此目录交付四份保持原字节的归档，覆盖五个已独立验收的有界原生运行。模型、事前 oracle、原始结果、历史失败、源代码和独立终结收据保留在各归档内。这里不新增案例验收、不修改发布索引，不把归档数量当作完成率。

| 归档 | 已验收范围 | 关键边界 |
| --- | --- | --- |
| [NOTE 与指南](K02-NOTE-and-guide-20261019-v2.zip) | 可选文本 NOTE 省略及 null 恢复；另一个新目录在中性 cwd 经指南入口完成原生 import-save/export。两次各完整 381 typed 格。 | 无 calc；不是任意缺键或默认值规则。 |
| [数值空列](K02-numeric-null-and-guide-20261019-v1.zip) | 省略 LINDX(integer)/MANHC(double) 两列及四个作者 null，完整回导 381 格。 | 仅 optional blank/null；无 calc。 |
| [活动 QTY 默认值](K02-active-QTY-null-default-and-guide-20261019-v1.zip) | 一个活动 Station 的 QTY=1 改为 null；完整 339 格仍保留 null，4044 报告格、全事件及日志与已接受父例一致。 | 观察行为符合文档默认 1；未观察内部默认展开，不推广其他默认值。 |
| [缺失 BSID](K02-missing-BSID-and-guide-20261019-v1.zip) | 活动 System.BSID 引用不存在的 System，在 calc 输入解释阶段报 error18；完整 339 格、错误日志、无效 SXO、无事件/报告及失败保留通过。 | 这是正确阶段的负例，三个原生进程 exit0，不是 import 拒绝或成功仿真。v100 工具协议失败仍在包内。 |

每个原生运行的唯一 runID、原 owner 及独立收据保留原始路径和哈希。已消耗的目录、runID、claim 与 GO 不能再运行或重建。归档中的旧指南、历史计划和未发布描述是冻结时的记录；本目录说明此次伴随归档交付的范围，不追溯修改它们。

## 仅靠本目录核验内容

从本次提交或独立交付记录取得 `archive-manifest.json` 的 SHA-256，然后在本目录执行：

```text
python -I -X utf8 -B verify_archives.py --manifest-sha <archive-manifest.json的SHA256> --replay
```

仅需 Python 3.12 标准库。入口验证本目录文件、四份 ZIP、全部内层索引文件和五份独立原生收据，再在临时新目录分别调用归档内冻结的只读 `replay.py`。支持 Windows 和 macOS；不需要作者的临时项目目录、SIMLOX 安装或凭据。回放不启动 SIMLOX，不加载包内 DLL，不重新证明 Windows 只读属性、原始句柄、互斥所有权或 GUI 保护。

各 ZIP 根目录的 `DELIVERY.md` 及案例 `DIRECTORY-GUIDE.md` 给出当次原生方法和明确主机前提。新的真实原生运行还需要匹配的 SIMLOX、许可证、编译器/Python/SSH、fresh GUI 身份、唯一执行权、串行 NativeQueue、新目录/版本/runID及事前独立审查；此归档回放不签发新的运行 GO。包内 DLL 为有来源记录的项目自编译守护/身份查询工具，内容回放不会执行；供应商程序、专有手册、数据库、凭据、完整会话与私有 minidump 不在归档中。

## 尚未完成

非 ASCII 导入崩溃与 inactive_rows 无损回导仍 NO_GO；wrong-QTY-type 仍违反原冻结非零导入合同；重复键 import 拒绝仍 HOLD。活动重复 STID 已观察 calc error2013，但其完整日志合同仍 NO_GO。缺引用的 import 拒绝、其他默认/必填键规则、A01 旧原生 helper 来源迁移、真正的新 agent 原生试用以及整体 Issue #18 尚未验收。

2026-10-19 loopback SSH 的新日志调用方式仅完成纯工具退出/协议验证，旧卡死根因未证明，也未集成到新的原生 profile；不要直接改动或重跑这些已消耗的原生入口。GUI 专属功能 OUT 不等于通过；CI/waiver、跨引擎一致性、性能和整体完成不由本目录证明。
