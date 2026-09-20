# Independent SimPy Reference Runtime Conformance

状态：2026-09-20，B1/B2/B3 及 F35 43 天 seeds `0、1、7` 已通过固定旧模型 oracle 验收。

## 独立边界

```text
canonical simulation_inputs JSON
  → compile_aircraft_support
  → serialized aircraft-support-plan/v1alpha2
  → SimpyReferenceRuntime
  → sample requests + trace + ledgers + metrics + terminal state
```

reference runtime 只读取 `ExecutionPlan`。`src/sim_engine_compiler` 不导入 `spare_mvp_abm`，也不导入、继承、实例化或调用 `AircraftSupportV1Model`。旧模型只在 `scripts/run_spare_mvp_oracle.py` 中通过文件边界生成固定 oracle。

Execution Plan 编译并索引化：

- `legacy-minute-v1` 的 15 个显式 phase；
- 飞机、任务、保障活动、稳定拓扑串行步骤和资源节点；
- 组件适用关系、故障树、失效率、维修活动和预防维修周期；
- 本地库存及纵向/横向供应路线、运输时间与批量上限；
- source input SHA-256、计划 fingerprint、业务规则 ID 和 source path。

## 手算切片

| 切片 | 固定输入 | 核心时间线 | oracle 结果 |
|---|---|---|---|
| B1 任务与日保障 | [b1-daily-operations.json](../tests/fixtures/synthetic/b1-daily-operations.json) | 20/40 起飞，30/50 返航，52 日终保障完成 | 终态、12 个核心指标、业务事件一致 |
| B2 故障与维修 | [b2-failure-repair.json](../tests/fixtures/synthetic/b2-failure-repair.json) | seed 0 样本 5.581821 分钟；第 11 分钟故障，第 14 分钟修复 | 随机请求、phase、维修方法、任务失败、资源账本一致 |
| B2 预防维修 | [b2-preventive-maintenance.json](../tests/fixtures/synthetic/b2-preventive-maintenance.json) | 第 1 分钟到期并开工，第 4 分钟完成 | 生命周期归零及终态一致 |
| B3 组织库存 | [b3-upstream-transport.json](../tests/fixtures/synthetic/b3-upstream-transport.json) | 第 1 分钟上级发运，第 3 分钟到达并唤醒，第 5 分钟完成 | 运输、库存消耗、终态和核心指标一致 |

测试另覆盖横向供应路线，以及任务取消后在下一 `transport_arrivals` phase 返还已到达但未消耗的预约库存。

## F35 43 天验收

固定 [canonical 输入](../tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json)来自上游提交 `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`，输入 SHA-256 为 `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`。编译后的 [Execution Plan](../tests/fixtures/spare_mvp/f35-43day-5352a0d/execution-plan.json)包含 9 架飞机、104 个任务、13 个活动、424 个组件和 18 个预防维修周期。

固定 oracle 位于 `tests/fixtures/spare_mvp/f35-43day-5352a0d/oracle/`。验收逐 seed 比较：

| seed | 随机请求 | 空中故障 | 发射/完成/失败架次 | 成功任务波次 | 取消架次 |
|---:|---:|---:|---:|---:|---:|
| 0 | 3816 | 13 | 148 / 135 / 13 | 66 | 60 |
| 1 | 3818 | 13 | 148 / 135 / 13 | 66 | 60 |
| 7 | 3820 | 14 | 178 / 164 / 14 | 77 | 30 |

以下内容严格相等：核心事件的时间、phase、类型和实体绑定；飞机、任务、作业、资源及库存终态；核心任务、故障、维修、预防维修与库存指标。随机请求的顺序、组件身份、分布和参数严格相等。Linux 与 macOS 的 `libm` 在指数采样值最后约 1–2 个二进制位可能不同，因此采样值采用 `rel_tol=2e-15, abs_tol=1e-12`；所有离散事件分钟和业务状态仍精确比较。

本次输入与早期性能报告的输入 hash `8e0a8c4a…` 不同，说明上游运行数据库内容曾变化。语义验收固定使用仓库内 `6b7730e1…` fixture，不读取活动数据库。

## 运行与验证

```bash
.venv/bin/python scripts/compile_execution_plan.py \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json \
  /tmp/f35-plan.json

.venv/bin/python scripts/run_reference_plan.py \
  /tmp/f35-plan.json /tmp/f35-seed-0.json --seed 0

.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

当前 21 项测试通过；全套包含三个 43 天样本，在本机约 31 秒完成。该耗时用于验证，不作为 Rust 加速结论。

## 后续边界

当前 compiler 直接从 canonical input lowering 到 Execution Plan，Business IR 与 Core Simulation IR 尚未单独物化。下一阶段应让 Rust runtime 读取同一份 Plan，并以本套 Python reference/oracle 差分测试作为语义门禁。
