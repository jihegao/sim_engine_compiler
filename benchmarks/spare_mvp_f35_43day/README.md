# spare_mvp F35 43 天对照基线

状态：2026-09-20 已在 AMD128 实跑通过。这里保存阶段 A 的上游 oracle 与性能基线，不是本项目独立编译器已经实现的证据。

## 输入与环境

- `spare_mvp`：`5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`，当时为 `main == origin/main`，原工作树干净。
- 数据库：AMD128 `/home/g/Models/spare_mvp/runs/system-start/spare_mvp.sqlite3`，只读打开。
- Project ID：`project-j16-8aircraft-43day-availability-20260727-copy-2`。名称是历史遗留；实际编译为 9 架 F35、104 个任务波次、43 天/61,920 分钟、423 个故障行为组件和 2 个保障节点。
- canonical inputs SHA-256：`8e0a8c4a5cc00e98e88bca0e2ab3a55876707ce6bee14e6c0918ed7b05061eef`。
- AMD128：Linux x86_64、Python 3.12.13、SimPy 4.1.1。
- 正式计时：种子 `0,1,7`，每种子 2 次；轮换路线顺序。每条路线包含单样本初始化、运行和结果构造，排除 Adapter、共享 IR 编译、JSON I/O、API 与多进程 Monte Carlo 调度。

## 首次运行发现并修复的基线漂移

未打补丁的当前主分支在种子 0 首轮失败：分钟基线 `postflight_count=4`，SimPy 为 `9`，首架飞机的 `postflight_due` 终态也不同。原因是业务内核新增 `daily-v1` 的两次 `_coordinate_operations_postflight()` 和截止时 `_finalize_operations_cutoff()`，SimPy 实验的手工阶段表仍停留在旧版本。

[补丁](patches/simpy-daily-operations-sync.patch)只同步这三个阶段调用；它在 detached 临时 worktree 中应用，未改 AMD128 主工作树。补丁后的 43 天冒烟及完整测试逐字段和终态一致。原失败报告保留在 [prepatch-failure-20260920.json](results/prepatch-failure-20260920.json)。

这次漂移证明事件 phase 表必须进入版本化语义合同，不能只藏在执行器代码中。本项目后续的 Python 与 Rust 后端都应加载同一份 phase plan。

## 结果

| 路线 | 中位总耗时 | 相对分钟基线 | 语义范围 |
|---|---:|---:|---|
| 分钟基线 | 16.290s | 1.00× | 原串行语义 |
| 状态触发 | 3.569s | 4.56× | 保留串行 |
| 编译结构 + 活动作业索引 | 3.346s | 4.87× | 保留串行 |
| 独立 SimPy 调度 | 3.396s | 4.80× | 保留串行 |
| 并行 DAG + 直接调度 | 3.554s | 4.58× | 改变飞前作业语义 |
| 并行 DAG + SimPy | 3.530s | 4.61× | 改变飞前作业语义 |

独立 SimPy 比编译结构路线慢 1.50%。本次证据支持“状态触发和活动集合索引是主要收益”；不能据此认为 SimPy 更快，也不能把 DAG 路线的业务结果与串行路线当作等价结果。

正式 36 次运行形成 24 组比较：18 组串行候选对分钟基线、6 组直接 DAG 对 SimPy DAG，`core_difference` 和 `terminal_state_difference` 均为空。正式计时前的真实案例预热累计通过 29,649 次不变量检查。

共享 IR 编译为 0.0444 秒，Adapter 为 0.7347 秒，均单列。原始数据见 [results-43day-20260920.json](results/results-43day-20260920.json)；公开小案例验证结果见 [verification-20260920.json](results/verification-20260920.json)。

## 复核

本地验证捕获报告的状态、路线集合、种子/重复次数、差分结果与中位数：

```bash
python3 benchmarks/spare_mvp_f35_43day/summarize.py
```

AMD128 的完整复跑步骤如下。`$WORKTREE` 应为从上述提交创建的隔离 worktree；补丁应用前先执行 `git apply --check`。

```bash
git -C /home/g/Models/spare_mvp worktree add --detach "$WORKTREE" 5352a0d7757cbac012c75d516d1a7ac4ff15aa2a
git -C "$WORKTREE" apply /path/to/simpy-daily-operations-sync.patch

cd "$WORKTREE"
/home/g/Models/spare_mvp/.abm-mesa-test-env/bin/python \
  experiments/compiled_routes/verify.py /tmp/f35-verification.json

/home/g/Models/spare_mvp/.abm-mesa-test-env/bin/python \
  experiments/compiled_routes/benchmark.py \
  --database /home/g/Models/spare_mvp/runs/system-start/spare_mvp.sqlite3 \
  --project-id project-j16-8aircraft-43day-availability-20260727-copy-2 \
  --seeds 0,1,7 --repeats 2 \
  --output /tmp/f35-results.json
```

此外，在补丁 worktree 上运行当前 `tests.test_aircraft_support_v1_model`：113 项通过。验证脚本还通过 117 组串行差分、2 组手算 DAG 调度、2,447 次不变量、3 种非法图拒绝和 6 组取消后备件归还唤醒检查。

## 适用边界

SimPy 路线拥有独立 generator/调度循环，但复用 `spare_mvp` 的任务、故障、维修、运输和原子资源分配业务方法。它是调度器对照，不是独立业务实现。下一阶段仍需将 canonical 输入编译成不依赖旧模型实例的 Execution Plan，再由本项目 Python reference runtime 执行；之后才能与本基线做真正的独立后端差分。

两条 DAG 路线将飞前作业从稳定串行改为依赖图并行，属于不同模型语义，只用于对照调度器之间的一致性。3 个工程种子不足以评价业务方案优劣。
