#!/usr/bin/env python3
"""CONTROLLER ONLY. Rebuild first-round-derived repair material and frozen evidence.

This authoring program may read first-round private controls. It must not be
shown to repair participants, and never reads the round-two holdout private area.
Existing output is refused so initial evidence cannot be silently overwritten.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PILOT = ROOT / "experiments/codex_modeling_pilot"
sys.path.insert(0, str(ROOT))
from experiments.codex_modeling_pilot import runner as pilot
from experiments.codex_modeling_pilot import evaluator
from experiments.codex_modeling_round2.repair.feedback import feedback_from_report, check_probe


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pilot.write_json(path, value)


def projection(pid, description, kind, where, fields, expected, derivation):
    return {"id": pid, "description": description, "type": "projection", "kind": kind,
            "where": where, "fields": fields, "expected": expected, "public_derivation": derivation}


def public_tasks():
    requirements = [
        ["观察4小时，每0.1小时报告一次。机队由raven-1、raven-2、raven-3三架utility飞机组成。",
         "准备工作叫prep：账面的整体准备估时为0.2小时，实际只有inspection检查这一步，每架检查0.2小时，各占用一名staff人员直到本机检查结束。班组一共只有两人，可在人员有空时同时服务不同飞机。",
         "patrol需要三架飞机成组出动。1.8小时接到通知，原定2小时起飞，最迟可延后0.3小时，实际起飞后飞行0.7小时。三架都检查完才能出动；调度优先级为1，没有前序任务。"],
        ["本题全部业务时间以分钟给出：观察180分钟，每6分钟报告一次。仅有一架utility飞机minute-1。",
         "任务minute-flight在第57分钟接到通知，第75分钟准时起飞，不容许延误，飞行42分钟。只需这架飞机，调度优先级为1，没有前序任务。",
         "准备工作prep总共18分钟，不再拆分步骤，也不占共享人员或设备。飞机成功返航后还须周转6分钟才能再次可用。"],
        ["观察4小时，每0.1小时报告一次。仅有一架utility飞机serial-1和一名staff人员。",
         "任务serial-flight在2.1小时通知、原定2.4小时起飞、容许延后0.2小时，实际起飞后飞行0.4小时。任务需要一架utility，调度优先级为1，没有前序任务。",
         "准备工作prep保留原来的账面整体估时0.9小时，用于既有的提前可行性检查；实际作业改为先做0.12小时的safety检查，再做0.18小时的warmup预热。检查时占一名staff人员，检查结束立即归还；预热不需人员。实际准备只执行这两步，不另加账面估时。准备完成且达到原定起飞时间后才能出动。"],
        ["观察2.4小时，每0.1小时报告一次。有cancel-1、cancel-2两架utility飞机，一名staff人员。",
         "准备工作prep的账面估时和唯一long-check检查步骤都是0.3小时，每架检查均占一名staff直到结束；另有instant准备，无耗时且无分解步骤。",
         "tight需两架飞机一起出动，在1.1小时接通知、原定1.4小时起飞、飞行0.4小时，使用prep，调度优先级为1。现在业务把容许延误改成0.29小时；若到最终起飞期限仍未准备齐，就取消并归还占用的飞机和人员，旧的准备完成事件不能再改变状态或重复释放。",
         "recovery是独立任务：1.69小时通知、1.72小时起飞，不容许延误，飞行0.23小时，只需一架utility，使用instant，调度优先级为2。它可接手刚被取消的任务归还的飞机，不依赖tight成功。"],
        ["观察4小时，每0.1小时报告一次。有lead-1（leader机型）和wing-1（wing机型），不需要共享人员或设备。两任务都使用prep，准备总共0.1小时、不拆分步骤。",
         "lead需要一架leader：1.4小时通知，1.6小时起飞，不容许延误，飞行0.8小时，调度优先级为1，没有前序任务。",
         "follow需要一架wing：1.8小时通知，原定1.9小时起飞，容许延后0.6小时，飞行0.3小时，调度优先级为2。它可以按自己的通知提前准备，但必须等lead成功返航才允许起飞。不能把lead接到通知、开始准备或起飞当作已完成。"],
        ["观察3小时，每0.1小时报告一次。仅有一架utility飞机fault-1。飞机故障后在本机直接维修0.35小时，不使用共享人员、设备或库存。",
         "飞机有一项名为flight-pm的维护：累计实际飞行达到1.1小时后，需要停机维护0.45小时。只计飞行时间，失败航次也累计，在返航时检查。已到期的维护不能因故障维修而免除；先修故障，再做应做的维护，完毕后才能再次出动。",
         "两任务都用零耗时的prep准备、不拆分步骤，各需一架utility且没有任务依赖。first在0.6小时通知并计划起飞，飞行1.3小时，不容许延误，优先级为1；next在2.25小时通知并计划起飞，飞行0.2小时，容许延后0.45小时，优先级为2。",
         "本题研究固定情景：fault-driver在1.05小时使正在飞行的fault-1发生故障。任务结果算中止，但飞机仍按原飞行计划返航，不提前结束航程。这是明确给定的外部故障，不需要随机生成故障，也不涉及库存或其他事件效果。"]
    ]
    titles = ["三机共用两人班组", "分钟业务时间与周转", "检查之后才能预热", "截止取消与飞机再利用", "成功返航后才能接续", "故障后按计划返航并维护"]
    return {"schema": "codex-modeling-repair-tasks/v1",
            "scope": "第一轮T01—T06业务场景的语义修复对照；不是第二轮留出自主建模成绩。",
            "profile": "aircraft-bounded-events/v1", "backend": "python-bounded-reference",
            "submission": "提交完整candidate，沿用R01—R06题号及给定实体名称。可根据业务要求修改初始模型；不要修改编译器或运行器。",
            "common_business_defaults": ["除各题明确说明外，飞机初始健康可用，无返航后周转、故障维修或预防维护；不配置换件、库存和运输，相关数量为零、关联为空。",
                "除R06明确给定的故障外，不生成故障，也没有任何外部事件。保留明确给出的飞机、任务、过程、资源及身份，不增删业务实体。",
                "所有输出时间统一换算为小时；给定调度优先级的数字越小越优先。未说明有前序条件的任务互不依赖。",
                "初始candidate可编译运行，但并非业务正确答案。最多提交两次修订；修改理由用简短业务解释，不需逐字复述字段。"],
            "tasks": [{"task_id": f"R{i:02d}", "title": titles[i-1], "initial_candidate": f"initial/R{i:02d}.json",
                       "requirements": text} for i, text in enumerate(requirements, 1)]}


def public_probes():
    return {"schema": "codex-modeling-repair-public-probes/v1", "arm": "T",
            "scope": "每题最多两个预注册业务行为探针；不检查完整模型结构，也不是最终验收。",
            "tasks": {
                "R01": [projection("R01-P1", "完整三机编队应在2.2小时出动。", "mission_started", {"mission": "patrol"}, ["hour"], [[2.2]], "两人先完成两架检查，第三架随后完成；完整编队再起飞。"),
                        {"id": "R01-P2", "description": "staff同时在岗人数不能超过两人。", "type": "resource_peak", "resource": "staff", "maximum": 2,
                         "public_derivation": "业务只提供两名共享人员。"}],
                "R02": [projection("R02-P1", "minute-flight应在第117分钟返航。", "mission_returned", {"mission": "minute-flight"}, ["hour"], [[1.95]], "第75分钟起飞，再飞42分钟。"),
                        projection("R02-P2", "飞机应在第123分钟完成周转。", "turnround_finished", {}, ["hour"], [[2.05]], "第117分钟成功返航后再周转6分钟。")],
                "R03": [projection("R03-P1", "实际步骤必须按检查、预热顺序启动。", "work_started", {"mission": "serial-flight"}, ["step"], [["safety"], ["warmup"]], "业务明确先检查后预热。"),
                        projection("R03-P2", "staff应在2.22小时结束检查时归还。", "resource_released", {"resource": "staff"}, ["hour"], [[2.22]], "2.1小时接到通知，检查历时0.12小时，预热不继续占人员。")],
                "R04": [projection("R04-P1", "tight应在1.69小时取消。", "mission_cancelled", {"mission": "tight"}, ["hour"], [[1.69]], "最晚起飞是1.4+0.29；一名人员串行做两架各0.3小时，赶不及完整编队。"),
                        {"id": "R04-P2", "description": "tight取消后不得再有其工作完成事件生效。", "type": "none_after", "kind": "work_finished", "where": {"mission": "tight"}, "after_hour": 1.69,
                         "public_derivation": "业务要求取消使先前排定的完成事件失效。"}],
                "R05": [{"id": "R05-P1", "description": "lead成功返航必须先于follow起飞被记录。", "type": "ordered_events",
                         "events": [{"label": "lead成功返航", "kind": "mission_returned", "where": {"mission": "lead", "outcome": "successful"}}, {"label": "follow起飞", "kind": "mission_started", "where": {"mission": "follow"}}],
                         "public_derivation": "lead成功返航才解除follow的起飞前置条件；同刻返航完成可以触发后续出动。"},
                        projection("R05-P2", "follow可以提前准备，并应在1.9小时准备完成。", "preparation_finished", {"mission": "follow"}, ["hour"], [[1.9]], "1.8小时通知加0.1小时准备；前序条件只限制起飞。")],
                "R06": [projection("R06-P1", "first虽因故障中止，仍应在1.9小时返航。", "mission_returned", {"mission": "first"}, ["hour", "outcome"], [[1.9, "aborted"]], "0.6小时起飞加原定1.3小时航程，故障不提前返航。"),
                        {"id": "R06-P2", "description": "故障维修结束后必须完成已到期维护，next随后才能起飞。", "type": "ordered_events",
                         "events": [{"label": "故障维修结束", "kind": "repair_finished", "where": {}}, {"label": "维护开始", "kind": "pm_started", "where": {}}, {"label": "维护结束", "kind": "pm_finished", "where": {}}, {"label": "next起飞", "kind": "mission_started", "where": {"mission": "next"}}],
                         "public_derivation": "first的1.3小时飞行即便失败也超过1.1小时维护阈值；业务要求先修复、后维护、再出动。"}]
            }}


def build():
    for name in ("public", "private"):
        if (HERE / name).exists():
            raise ValueError(f"refusing to overwrite frozen material: {HERE / name}")
    original = pilot.read_json(PILOT / "private/oracles.json")["tasks"]
    write(HERE / "public/tasks.json", public_tasks())
    probes = public_probes()
    write(HERE / "public/probes.json", probes)
    guide = (PILOT / "public/schema-guide.md").read_text(encoding="utf-8")
    guide = guide.split("Only the experiment's execution-feedback arm")[0]
    guide += "\n修复实验由控制器执行反馈工具。参与者只读取分配条件的feedback.json，不得自行调用运行器或浏览internal/private目录。\n"
    (HERE / "public/schema-guide.md").write_text(guide, encoding="utf-8")
    shutil.copyfile(PILOT / "public/mechanisms.md", HERE / "public/mechanisms.md")
    mutations = {
        "R01": "共享staff容量误设为3，使三机可同时检查。",
        "R02": "飞行42分钟与周转6分钟错误按百分之一小时转换为0.42与0.06。",
        "R03": "串行步骤顺序颠倒，预热先于检查，人员释放时间也随之改变。",
        "R04": "tight仍保留旧的0.3小时容许延误，改变截止与同刻完成的先后结果。",
        "R05": "遗漏follow必须等lead成功返航的依赖。",
        "R06": "将维持原定返航的故障错误建模为立即损伤返场，连带改变飞行累计及维护。",
    }
    evidence, mapping = [], {}
    for i in range(1, 7):
        tid, rid = f"T{i:02d}", f"R{i:02d}"
        mapping[rid] = tid
        target = deepcopy(original[tid]["internal_control"])
        target["task_id"] = rid
        target["reason"] = "控制器保留的第一轮业务目标，禁止向参与者展示。"
        bad = deepcopy(target)
        bad["reason"] = "待复核并修复的初始业务模型。"
        model = bad["model"]
        if i == 1:
            model["resources"][0]["capacity"] = 3
        elif i == 2:
            model["missions"][0]["duration_hours"] = 0.42
            model["aircraft"][0]["turnround_hours"] = 0.06
        elif i == 3:
            model["processes"][0]["steps"].reverse()
        elif i == 4:
            model["missions"][0]["delay_hours"] = 0.3
        elif i == 5:
            model["missions"][1]["depends_on"] = []
        elif i == 6:
            model["external_events"][0]["operation"] = "damaged_arrival"
        write(HERE / f"public/initial/{rid}.json", bad)
        write(HERE / f"private/targets/{rid}.json", target)
        reports = {}
        for label, candidate in (("initial", bad), ("target-control", target)):
            report = pilot.run_candidate(candidate, HERE / f"private/evidence/{label}/{rid}", score=False)
            scored = deepcopy(candidate)
            scored["task_id"] = tid
            evaluation = evaluator.evaluate(scored, report["result"])
            write(HERE / f"private/evidence/{label}/{rid}/independent-evaluation.json", evaluation)
            reports[label] = report
            if not (report["compiled"] and report["executed"] and report["error"] is None):
                raise AssertionError((rid, label, report["error"]))
            if evaluation["accepted"] != (label == "target-control"):
                raise AssertionError((rid, label, "unexpected independent score"))
            results = [check_probe(report["result"]["trace"], probe) for probe in probes["tasks"][rid]]
            if label == "target-control" and not all(p["passed"] for p in results):
                raise AssertionError((rid, "target must satisfy public probes", results))
            if label == "initial" and not any(not p["passed"] for p in results):
                raise AssertionError((rid, "initial must expose at least one public discrepancy"))
            evidence.append({"task_id": rid, "score_task_id": tid, "variant": label,
                             "compiled": report["compiled"], "executed": report["executed"],
                             "accepted": evaluation["accepted"], "fingerprints": report["fingerprints"],
                             "failed_checks": [c["id"] for c in evaluation["checks"] if not c["passed"]],
                             "public_probes_passed": [p["id"] for p in results if p["passed"]]})
        for mode in ("N", "D", "T"):
            write(HERE / f"public/feedback/{mode}/{rid}.json", feedback_from_report(reports["initial"], mode))
    write(HERE / "private/task-id-map.json", mapping)
    write(HERE / "private/mutations.json", mutations)
    write(HERE / "private/initial-diagnostics.json", {"schema": "codex-modeling-repair-initial-verification/v1", "evidence": evidence})
    sources = [PILOT / "public/tasks.json", PILOT / "private/oracles.json", PILOT / "evaluator.py", PILOT / "runner.py"]
    material = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    write(HERE / "private/frozen-material.json", {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "author": "继承当前模型的独立AI题作者；非人类作者；未读取round2/private留出材料。",
        "scope": "第一轮T01—T06派生的修复对照；不计入第二轮留出自主建模成绩。",
        "max_revisions_per_case": 2, "task_id_map": mapping,
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "material_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(material)},
    })
    print(json.dumps({"prepared_cases": 6, "initial_compiled_and_executed": 6, "initial_rejected": 6,
                      "target_controls_accepted": 6, "initial_feedback": "public/feedback/{N,D,T}/R01..R06.json"}))


if __name__ == "__main__":
    build()
