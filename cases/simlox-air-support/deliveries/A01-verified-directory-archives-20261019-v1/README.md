# A01 固定模型与 STIM9 参数模型：已验收目录归档

这里交付两份原字节 ZIP，保存已经独立验收的固定 A01 和 STIM8→9h 参数子例的目录工具、输入来源、事前 oracle、原始结果、日志及终结收据。发布归档不增加原生运行、语义案例或 `publication-index-v1.json` 条目，也不代表 K02 或 Issue #18 整体完成。

| 归档 | 已验收范围 | 限定 |
| --- | --- | --- |
| [固定 A01](A01-case-local-native-and-guide-20261019-v1.zip) | 原输入保持不变，项目 helper 来源迁入独立案例目录；中性 cwd 的冷进程目录入口完成 import-save、export、单线程 calc、jsonreport。 | 339 typed 回导格、4044 报告格、全事件和四日志；18 对原始/恢复文件、180 个实际句柄关闭及 GUI/队列保护均独立核对。 |
| [STIM9 参数子例](A01-STIM9-directory-derivation-and-guide-20261019-v1.zip) | 仅靠准备目录、脚本和其中固定 A01 源归档实际准备工具；目录内冷进程派生唯一 STIM8→9h 变化，再完成上述四阶段原生。 | 40398 字节输入仅改变一个业务格/一个字节；339 回导格、4044 报告格、完整事件/日志和同等原始 OS 保管链通过。准备所用父 ZIP 与本目录固定 A01 归档逐字相同。 |

两次运行各四个子进程一次 Resume、自然 exit0，各 calc1/成功仿真1；通知和任务时序、飞行2h/ready33h/NPSTA0/终态ready1均符合各自运行前冻结的完整预期。STIM9 的任务从8–10h移至9–11h。raw 报告保留供应商历史尾逗号；完整 raw 字节相等后才使用既有独立 normalized 参考，不修写 raw 或 oracle。

## 仅靠此目录回放交付内容

从本次提交或独立交付记录取得 `archive-manifest.json` 的 SHA-256，执行：

```text
python -I -X utf8 -B verify_archives.py --manifest-sha <archive-manifest.json的SHA256> --replay
```

Python 3.12 标准库入口核对两份归档、1089 个内层索引文件、两份权威原生终结收据、STIM9 准备目录的父归档，再在新临时目录运行各包冻结的只读回放。支持 Windows/macOS；内容回放不依赖作者临时项目目录或 SIMLOX，不执行 prepare、PowerShell、DLL 或原生模型。Windows 的 readonly/NTFS 身份、原始 H、NativeQueue 和 GUI 证据不能在内容回放时重建，以各包实际独立终结收据为准。STIM9 内含的父 ZIP 是准备输入，不计为第三项新验收。

各归档 `DELIVERY.md`、案例 `DIRECTORY-GUIDE.md` 及 STIM9 `preparation/PREPARE-GUIDE.txt` 说明当次方法和主机前提。所有固定路径、runID、claim、GO 和准备目录已消耗，不能照旧重跑或重建 GO；未来原生工作需要独立的新目录/版本/runID、fresh 来源与 refs/settings、GUI 完整身份、唯一执行及串行队列、正常预检和独立门禁。本次证明的是声明主机前提下的固定目录方法，不是任意路径 factory 或未来自动运行批准。

包内保留有来源记录的项目自编译保护/身份查询工具，内容回放不执行它们。供应商安装程序、专有手册、凭据、数据库、完整会话和私有 minidump 均未纳入交付。匹配 SIMLOX/许可证、Python/.NET/SSH、既有信任及受保护协调进程、GUI、实时仓库门禁仍是明确前提。

## 当前边界

新日志 SSH 在上述固定 v27 和参数 v29 两个有限 profile 中完成实际原生集成与独立验收；旧挂起根因或旧方式修复仍未证明。旧归档中的历史描述、失败和未发布字段保持原字节，当前交付范围以本目录和发布验收收据为准。没有真正独立新 agent 参与，不能将同聊天冷进程试验称为新 agent 原生交付。

K02 非 ASCII 导入崩溃、wrong-QTY-type 原冻结 import 拒绝合同、inactive_rows 无损回导仍 NO_GO，duplicate import 拒绝仍 HOLD；活动重复键的完整日志合同也未通过。正确 calc 阶段 BSID 负例不等于 import 拒绝，其他默认/必填键/引用规则仍有缺口。GUI 专属功能 OUT 不等于通过，跨引擎、性能、CI/waiver 和整体 Issue 完成均不由此归档交付证明。
