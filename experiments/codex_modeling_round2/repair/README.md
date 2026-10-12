# 第一轮场景派生的语义修复对照

本目录是第二轮实验中的独立修复对照，业务来源于第一轮 T01—T06。
它检验给定错误模型在不同反馈条件下的修复，**不属于第二轮留出题的自主建模成绩**。
题目和初始错误由继承当前模型的独立 AI 作者准备，非人类出题或复核；作者未读取
`experiments/codex_modeling_round2/private` 留出题材料。

六份初始模型都须通过既有三层编译与 Python reference 运行，但被第一轮独立
evaluator 拒绝。目标可由当前 profile 表达，目标对照必须完整评分通过。
任务号 R01—R06 在最终评分时仅在内存中映射到第一轮 T01—T06；模型和运行结果不变。

## 接口与下发

公共题面为 `public/tasks.json`，初始完整候选为 `public/initial/R01.json` 至
`R06.json`，共用 `public/schema-guide.md` 与 `public/mechanisms.md`。
题面用业务语言给出要求；完整输出格式由通用 schema 说明。

| 条件 | 初始反馈与后续反馈 | 可读取的额外文件 |
|---|---|---|
| N | 仅确认收到，不编译、不执行 | `public/feedback/N/` |
| D | 仅候选结构和编译诊断，不执行、无运行时错误反馈 | `public/feedback/D/` |
| T | 编译和执行诊断，加轨迹摘要和固定公开探针差异 | `public/feedback/T/`、`public/probes.json` |

每组使用 fresh agent，不继承题作者、评价者或另一条件的上下文。每题固定两次
修订机会：提供初始反馈，提交r1后给一次相应条件反馈，再提交r2（可保持不变）。
r2之后不再给任何反馈，由主控制器隐藏评分。保存初始、r1、r2候选及前两次反馈；
不得让agent依据隐藏评分再修订。初始证据与探针均在参与者开始前固定。

**必须在参与者提示中明确隔离：** 只可读取上述共用公共材料、分配条件的反馈、
自己的候选文件；不得浏览 `private/`、任意 `internal/`、其他条件反馈、
`prepare.py`、第一轮私有文件/提交/结果、第二轮主实验材料或其他代理上下文。
N/D不得读取T的探针或轨迹。参与者不得自己调用编译/运行器、评分器或修改实验工具。
此处采用控制器提供反馈的提示隔离，并非操作系统文件权限隔离，应在报告中明确。

控制器保存参与者候选后执行：

```bash
python experiments/codex_modeling_round2/repair/feedback.py \
  --candidate PATH_TO_CANDIDATE \
  --out EMPTY_OUTPUT_DIRECTORY \
  --mode N
```

`--mode` 可为N/D/T。唯一回传给参与者的文件是输出目录下的 `feedback.json`。
完整候选及相应条件产生的内部产物在该目录的 `internal/` 内保存，禁止参与者
浏览。N仅保存原始收件，不编译或执行；D复用既有候选校验、导入、lower、compile与
三层roundtrip，只编译、不实例化运行时。T调用`pilot.run_candidate(..., score=False)`，
保存完整三层文档、轨迹、诊断及哈希。反馈程序不导入私有评分器、不读私有材料。
错误JSON也保存原始提交，D/T可见解析诊断；N仍只回收件确认。

`public/probes.json` 每题只有1—2项由公开需求手算推出的轨迹预期/不变量，不比较
模型字段，不提供目标模型或修复补丁。T反馈的`public_probes[].discrepancy`给出
探针期望与观察差异。探针全部通过只代表局部符合，不是完整验收。

## 控制器准备与验证

`prepare.py` 仅供控制器使用，从第一轮private oracle读取目标对照并注入冻结错误，
生成公共材料和 `private/evidence/{initial,target-control}/Rxx/` 的完整初始证据。
它拒绝覆盖已有 `public/` 或 `private/`；重跑须在隔离副本中移开旧产物，禁止覆盖
已下发实验。主实验材料不在该脚本的读写范围内。

```bash
python experiments/codex_modeling_round2/repair/prepare.py
```

控制器摘要在 `private/initial-diagnostics.json`，内部任务映射在
`private/task-id-map.json`；`private/frozen-material.json`保存来源和材料SHA-256。
每个初始和目标模型都通过未修改的runner执行，再独立调用旧evaluator。
准备阶段要求：6/6初始编译运行成功、6/6初始被拒绝、6/6目标通过、6/6初始至少
一个公开探针失败、6/6目标公开探针全部通过。

最终评分由主控制器复用第一轮evaluator：复制完整candidate，仅将顶层task_id
按映射改成Txx，传入同一模型实际运行出的result。评分同时检查第一轮的精确结构、
行为轨迹、输入绑定及资源账本，较局部公开探针严格。因此报告应分别披露编译运行、
公开探针和完整评分，勿把编译成功或局部探针通过等同语义正确。
