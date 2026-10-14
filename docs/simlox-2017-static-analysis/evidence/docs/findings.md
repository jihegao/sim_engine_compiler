# SIMLOX 仿真算法与计算流程：手册证据

分析时间：2026-10-13。只读安装目录；本文件是独立证据笔记，不是二进制反编译结论。

## 来源与定位方式

- 手册：`C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf`，©2017 Systecon AB，共996物理页。
- 数据字典：`C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt`，原始拷贝留在分析机器，引用行号从1起；本 PR 仅提供笔记与源文件哈希。
- 原分析机器已用 pypdf 提取全部文本（未上传本 PR）：`SIMLOX_extracted.txt`、`manual_pages.json` 和 `page_NNNN.txt`。下文 pN 同时表示 PDF物理页N、手册印刷页N。关键 p224、230、233 已用 Poppler 渲染并目视核验，页码一致。
- 标签：**明示**=手册/字典明确陈述；**推断**=由规则重建；**未知**=文档不足，需二进制或运行证据。

## 1. 核心算法性质与可重建流程

**明示**：这是事件驱动、以任务需求带动维修和备件网络的随机仿真，评估给定资源/库存配置，而非在SIMLOX内优化库存或计算成本。p13原文短引：“SIMLOX is an event driven simulation tool”；p173：“actual event sequences generated in the simulation”。p173-175说明与OPUS10共享组织/物料建模，但SIMLOX MoE从实际事件序列收集；p174明确不计算成本。

**推断**：足够保守的高层流程如下，顺序不是已验证的机器实现：

1. 读取并检查关联表、按 Control.APID 选库存/资源/维修配置（p229-231）。
2. 为一个 replication 初始化部署系统、库存、资源、PM预寿命；展开任务/班次/运输/数据变更日程。
3. 任务预告触发系统分配、重构、准备；到启动时间检查最低系统要求。
4. 执行任务 OUT / ON STATION / BACK 三阶段；随机故障/损伤、PM期限、资源故障可能中断或挂起活动。
5. 返场执行 turnround，再生成系统维修及后续物料维修；替换需求沿供应链传播，缺件形成队列。
6. 备件到货、资源可用、维修/PM/运输结束等事件释放等待活动；系统恢复后重新参与任务分配。
7. 仿真在 SIMPE 强制结束；按结果窗口/区间保存状态平均、业务量、快照；更新跨replication平均与标准误。
8. 到 NREPS 上限，或满足 TCLEV 规则时结束。

**未知**：事件日历数据结构（堆、链表等）、同时间事件顺序、零延迟事件调度、时间推进内核精确调用链、每replication的初始化/释放顺序。不能因手册使用事件一词就宣称恢复了这些实现。

## 2. 运行长度、随机数、重复样本、预热

**明示（p230）**：NREPS 是最大replication数；SIMPE 是单次时长，无论任务profile是否结束都在SIMPE终止；最终结果跨replication求平均。随机发生器基于Lehmer方法，原文短引：“One single random number stream is used for all stochastic processes”。相同RSEED生成相同随机流、事件序列和结果的声明应理解为同一模型/同一版本下的复现承诺。RSEED建议大奇数。

**明示（p233、553）**：TCLEV默认0表示关闭自动收敛检查；允许0..0.5，超过0.1警告。停止条件为任务时间完成率 MTMF 的相对标准误 RSMTMF **连续10次replication低于TCLEV**，仍受NREPS上限约束。p233短引：“in 10 consecutive replications”。相对标准误由每次MTMF样本更新，标准误再除以MTMF均值；p553说明复制数扩大4倍通常令标准误缩小一半。通用可重建公式 `SE(mean(x))/mean(x)`，但内部方差分母、在线更新算法、均值为零的处理未知。

**明示（p20）**：不同replication可并行执行；**未知**：种子跨replication分配、跳跃长度、线程间RNG安排。不能把“单流”断言扩展为“所有线程共享一个全局可变RNG”。p24说明版本改变事件序列，单次replication结果可能变化，不能跨版本承诺位级复现。

**明示（p231）**：RCINT是结果区间分辨率/收集间隔，不是仿真积分步长。每区间状态型输出保存区间平均，业务量型保存区间总量。RCSTA/RCEND控制结果保存及报告时间窗口；一般控制值可由 ResultCollection 和 ResultCollectionProfile覆盖。

**未知/重要界限**：全文对 warm-up / warm up / burn-in 无命中，也未找到专门预热控制字段。RCSTA能避开初始时段的报告，但手册没有说明它清空累计量或提供稳态预热算法。不能称它为显式warm-up。

**明示（p202、204-205）**：Prelifing是设置部署物料和库存的初始年龄，避免PM同步。它只影响到下次PM的距离，对泊松CM故障间隔无年龄影响。例如PM间隔100小时，年龄60则剩40；年龄120则剩80（下一整数倍间隔）。字典行546-559给出FIXED、EQUIDIST、RANDOM、INHERIT，以及AGE/AGEMIN/OPID。预寿命初始化不能直接等同于运行预热。

## 3. 故障与损伤随机生成

**明示（p189-192）**：故障按泊松过程发生，因此间隔服从指数分布。传统模型以系统/零件FRT及AFFRT/SCFRT/ENVF等因素决定强度，沿物料分解按子件故障率占母件故障率的比例随机归因；母件率减子件合计率给出直接维修/非子件故障的剩余概率。可重建数学关系 `P(child s | parent failure)=FRT_s/FRT_parent`（必须考虑数量与应用因子，不能直接拿未归一原始字段套用）。同一件在一个任务中仅失败一次，但系统可有多个故障；QTYPM>1时同类型可有多个实例故障。

**明示（p190、183-184）**：任务期间与准备期间失效率分别可用MFF/PFF调整；PFF默认0。日历时失效不受这些任务倍率影响；多操作参数总故障强度相加。非关键故障可按时间或数量容限升级为关键；维修关键故障优先。

**明示（p190-192）**：failure-mode模型按FRQ生成故障模式，使用 CMLocation/CMReplacement 显式描述维修和多个零件替换；一个故障可涉及多个零件，等待和替换可并行，最久等件决定母件的拖延。部分替换概率与PM检出故障使用随机抽样。

**明示（p192-193、438-439）**：损伤有两种机制：DAMP每任务抽是否发生，然后发生时刻均匀分布在任务时长内，每损伤类型每任务至多一次；DAMRT用指数间隔，同类型可多次发生。两字段互斥；DAMP不允许用于continuous任务。损伤只在任务开始后发生，任务内各系统的损伤视为独立；每个后果再按自身概率抽样。ATTRITION使系统永久丢失，不返场；零件损伤可覆盖已有故障。

**推断**：指数间隔可用逆CDF `-ln(U)/lambda` 重建数学模型；**未知**：SIMLOX实际是否采用这个精确变换、U开闭区间、Lehmer常数与模数、率随操作变化时残余间隔处理。

## 4. 任务选择与系统状态

**明示（p180-183）**：任务有 OUT / ON STATION / BACK 阶段；random profile每replication先抽任务数量，再按等距或独立均匀时刻布置。regenerative任务由前任务预先启动后继，使后继抵达ON STATION时前驱开始BACK。预告期NOPER内分配、重构、准备。

固定/regenerative任务需要达到最低数量才能启动，不足则等到允许延误期；continuous/extendable按时启动，但不足则挂起。关键失效默认使系统返场；低于MNOSA使fixed/regenerative整体中止，continuous/extendable挂起，之后可补充系统。

**明示（p183）**：任务达到 MSUCPT 成功点后即使随后中止也算成功；continuous/extendable任务永不记为abort，因此总按成功记录。返场turnround若所需资源不足不分配资源，等待满足后才开始。

**明示（p184-187）**：系统分配顺序是ready pool、soon-ready、其他较低优先任务；ready pool内无故障优先于仅非关键故障。soon-ready不包括等件/等资源或有待处理关键PM的系统。mission优先级之后按计划开始时刻排序；每优先级组先两轮通知：先满足各任务最低需求，再补足名义数量。与系统类型偏好、显式formation、重构、单位组优先级共同作用，不能简化为单个FIFO。显式formation覆盖NOS/MNOS/MNOSA数量字段。重构REMOVE/REPLACE并行，一旦开始必完成；估计重构延误不计资源等待（p185、189）。

## 5. 维修、补给、资源竞争

**明示（p211-213、226-227）**：六类维修任务可拆成按序子任务，等待资源延迟后续任务。替换至少有REMOVE→REPLACE；REMOVE完成后故障件进入维修/运输，REPLACE开始前必须有替换件。替换需求在维修任务启动时立即发送；直接维修至少含REPAIR。主任务显式子任务时长覆盖主任务时长。系统可同时有多维修任务；全都完成才恢复。

非关键维修发出替换需求后，等到备件在手才真正开始其他动作；此前系统可再派任务，维修挂起但备件需求仍有效。资源/物料竞争时维修排序按“到系统可用的最短剩余时间”，系统多维修的时间估计由最长维修决定；非关键始终低于关键。p213短引：“shortest time to an available system”。PM资源排序还考虑关键故障最大维修时间加关键PM总时长（p217-218）。

**明示（p210）**：零件为被动对象，STATION / TRANSPORT UP / IN REPAIR / STOCK / TRANSPORT DOWN状态；一般装在系统上时并不始终显式建模，拆下才创建实体，装回母件后独立实体消失；受监控PM零件例外。

**明示（p215-216）**：维修比例是累计能力。故障生成时抽复杂度0..1，每站比较该复杂度与累计维修比例；复杂度低于能力在该站维修，否则继续上送。文档只说random draw，并未明确其分布为Uniform(0,1)，比例解释强烈暗示均匀抽样，但应列为推断。

**明示（p218-220）**：库存不足生成FIFO backorder；ENBOP可把有下游backorder的支持站需求提到前面。FAST需求可先于故障件到达上送；SLOW或仍需等维修决策则待故障件。支持站有DFRAC选择概率。到货先消除欠单，无欠单再入库。

**明示（p216-218）**：库存式再订货：报废量达到ROSIZ触发固定批量；时间式按ROINT日程订到名义库存STSIZ。交付时长固定或LEADTD随机，LEADT可提供均值。

**明示（p220-221）**：运输默认按需，或按固定日程/最小批量。启动一个计划运输时再创建后继运输。运输时长可随机；横向补给运输永远按需且时长不随机。

**明示（p221-223）**：资源故障也按泊松过程，故障后暂停自身故障生成；资源维修无须其他资源，只延迟MDT/分布。班次限制资源可用量和最大使用时间。横向补给仅在估计常规供应更慢时采用，其常规等待估计忽略高层短缺，可能偏乐观。抢件(robbing)针对关键替换维修，选择最长剩余等待的供体，估计不得拖慢供体/受体；资源等待可使抢件决定偏离最优。failure-mode显式CM任务不支持robbing。

**明示（p224，已视觉核验公式）**：传统维修额外移除次数 `N_extra ~ Poisson(NXRM)`，其中 `NXRM = sum(frac_s*(RRF_s-1))/sum(frac_s)`；额外件无故障概率 `pnf=(NFFF-1)/(RRF-1)`，要求RRF>=NFFF。额外移除串行，failure-mode多件替换并行。RRF=1时公式的边界处理未知。

## 6. PM与持续时间分布

**明示（p202-205）**：PM由任务次数、任务小时、日历时间等计数器达到间隔触发，不按故障泊松过程生成。多参数最先到期触发并重置其他计数；提前阈值创建非关键PM，超延期阈值升级关键。ENREG保持名义周期，延迟一次后提前下次以防漂移。PM活动的执行时长、替换/检出结果仍可随机。

**明示（p541-545）**：TimeDistributions / IntegerDistributions 支持基分布混合与嵌套；PFAC按分量给发生概率，总和应为1。正态时间分布在0左截断。Task/repair/reorder若显式均值缺省则使用分布均值；有给定时长可按该均值使用分布（p212、216）。**未知**：精确缩放实现、每基分布随机抽样算法、截断正态用拒绝采样还是逆CDF。

**文档矛盾**：p542-543的Integer说明疑似从Time复制，列出时间分布；字典行234-240才明确Integer.BASED枚举为 `<POISSON>, <DETERM>, <IRECT>`。Time字典行861-867枚举 `<TRIANG>, <LOGNORM>, <DETERM>, <RECT>, <EXP>, <GAMMA>, <NORMAL>`；PDF使用TRIANGULAR/LOGNORMAL/NEGEXP等长名称。支持哪种别名必须以解析器或输入试验确认，不能照手册复制。

## 7. 指标与统计语义

**明示（p552-554）**：MTMF=实际完成的活跃任务时间/规定任务时间；STMF=实际系统任务工作时间/规定系统时间，两者不含准备及turnround。MSTF=启动fixed任务数/规定fixed任务数；MSUF=达到成功点的fixed任务数/规定fixed任务数；regenerative不计入后两者。每replication更新这些量及其相对标准误。

**明示（p546-549）**：独立replication结果可选保存TOTAL/TIME/SNAPS，涵盖物料、任务、资源、总库存、系统，快照的字段少于区间/总量。**明示（p633）**：NSYA含ready与assigned-to-mission，非关键故障系统在维修未启动前也计为可用；“可用”不是“完全无故障”。

**明示（p230、116、860）**：分位数需足够replication，手册说NREPS需超过`1/(1-P/100)`，其他段落99%示例写至少100，严格/非严格边界存在文本差异。**未知**：排序插值、分位数样本选择和精确边界。

**明示（p564-565、633-634、645-646、723）**：MTLOW、NSYAL、SYDTU、NBOU的跨时间平均/总量必须对每次replication的均值/总量先形成样本，再取分位数，不能把区间分位数简单平均/相加。**文档差异（p571）**：STLOW跨时间却描述为平均区间分位数而非均值样本分位数；需动态结果比对确认，不能把统一聚合规则强套所有指标。

## 8. 数据字典交叉映射

| 计算环节 | 表/字段 | 字典行 |
| --- | --- | --- |
| 重复与随机控制 | Control.NREPS/SIMPE/RSEED/TCLEV/ENLOG | 137-160 |
| 结果窗口 | Control.RCINT/RCSTA/RCEND；ResultCollection/Profile | 141-143；689-702 |
| 任务日程 | OperationProfile.ITYPE/IQTY/IQTYD/IPER/IDISP/DTIM | 473-480 |
| 任务门槛与成败 | MissionType.NOS/MNOS/MNOSA/DURN/MSUCPT/MPAT | 447-462 |
| 维修任务资源 | TaskBreakDown.SEQ/DURN/DURND；TaskResource；SubTaskResource | 836-855；767-775 |
| PM计数/容限 | MaterielPM.PMINT/OPID/ATIM/DTIM/ENREG/MNOCC | 336-347 |
| 初始PM年龄 | PrelifeData.TYPE/AGE/AGEMIN；PrelifeDataAge | 546-559 |
| 资源可靠性 | ResourceStationData.RMTBF/RFTT/RMDT/RMDTD | 673-681 |
| 运输日程/分布 | TransportPolicyProfile.STIM/IINT/MINBS/TPTIM/TPTIMD | 868-877 |
| 分布混合 | IntegerDistributions / TimeDistributions.PFAC/BASED/PARAM1..3 | 234-240；861-867 |

数据库字段只证明数据契约，不能单独证明内核按所述方法实现。字典RSEED类型写Text而PDF写Integer，TCLEV字典仅非负而PDF设0..0.5，这些也应通过读取器验证。
