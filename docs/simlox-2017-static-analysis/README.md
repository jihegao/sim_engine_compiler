# SIMLOX 2017 静态分析审阅包

此目录支持[分析报告](../simlox-2017-static-analysis.md)。调查开始于 2026-10-13，完成于 2026-10-14（Asia/Shanghai），使用 REA 6.4.0 与 Ghidra 12.1.4，针对报告内固定 SHA-256 的本机原生程序。

- [REA 函数索引](evidence/rea/evidence-index.md)：38 个函数，伪代码与完整汇编摘出。
- [独立汇编核对](evidence/binary/binary-findings.md)：普通 PE/Capstone 观察与推断。
- [手册规则笔记](evidence/docs/findings.md)：页码与文档层面的已知／未知。
- [来源及完整性清单](provenance.json)：原始响应、证据包、会话快照、源文档及提交文件哈希。

伪代码不是原始源码，不能直接编译；浮点参数类型和调用签名需以指令核对。REA JSON 是派生的审阅摘出，原始 Evidence ID 只是来源标识，不能声称摘出副本就是 canonical Evidence。完整原始返回值、证据包和快照保留于原分析工作区。

此 PR 只提交报告、分析摘出和来源记录。SIMLOX 可执行文件、安装 DLL、工具包、许可数据、PDF 全文、数据字典全文、模型数据库和完整字符串清单均不在提交内容中。原程序保持只读，分析前后 SHA-256 一致；本次未执行 SIMLOX 仿真，也未进行与本项目的逐事件差分。报告不改变已有 profile 或接受范围，不构成原生等价或性能验收。
