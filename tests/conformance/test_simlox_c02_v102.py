"""C02 source deltas and joint-resource event-order controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/C02-joint-resources-v1.0.2"
sys.path.insert(0, str(CASE))
for name in ("build", "validate"):
    spec = importlib.util.spec_from_file_location(f"c02_{name}", CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"c02_{name}"] = module
    if name == "build":
        sys.modules["build"] = module
    spec.loader.exec_module(module)
BUILD, VALIDATE = sys.modules["c02_build"], sys.modules["c02_validate"]


def fake_table(name: str, records: list[dict]) -> dict:
    columns = list(records[0])
    return {"name": name, "columns": [{"name": column} for column in columns],
            "instances": [{"rows": [[record[column] for column in columns] for record in records]}]}


def fake_report(serial: bool, success: bool) -> dict:
    summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(success), "MSUF": int(success)}
    system, resource = [], []
    for index in range(72):
        hour = index / 2
        system.append({"STINT": hour, "ETINT": hour + .5, "NSYA": 1,
                       "NPSTA": int(hour == 7), "NPSUC": int(success and hour == 7.5),
                       "NSYMP": 1 if hour == 7 else 1 / 6 if not success and hour == 7.5 else 0,
                       "FTMO": int(success and 8 <= hour < 10),
                       "NSYMO": int(success and 8 <= hour < 10)})
        resource.append({"STINT": hour, "ETINT": hour + .5, "NR": 2 if success else 1,
                         "NRUM": (2 / 3 if serial else 2) if success and hour == 7 else 0,
                         "NRW": 1 if not success and hour == 7 else 1 / 6 if not success and hour == 7.5 else 0})
    return {"report": {"tables": [fake_table("ResultSummary", [summary]),
                                   fake_table("SystemResults", system),
                                   fake_table("ResourceResults", resource)]}}


def fake_log(serial: bool, success: bool) -> str:
    tag, owner = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<TEACH-AIR-01,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    crew, equip = "<P-CREW at <BASE-01,0>>", "<E-GSE at <BASE-01,0>>"
    duration = "0.166667" if serial else "0.5"
    end = 7.16667 if serial else 7.5
    events: list[tuple[float, str]] = [
        (7, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (7, f"{tag} mission created:"),
        (7, f"{tag} mission allocates system: {owner}"),
        (7, f"{owner} preparation started, mission: {tag}"),
        (7, f"system preparation task 0 on {owner} started"),
        (7, first + " started"),
        (7, first + " requests resources"),
        (7, first + " resource availability test"),
    ]
    lines = [f"Time: {hour} {body}" for hour, body in events]
    lines += [f"  Availability test on  {crew} request for: 1 OK",
              f"  Availability test on  {equip} request for: 1 {'OK' if success else 'failed'}"]
    if success:
        actions = [
            (7, first + " books resources"),
            (7, crew + " allocated to maintenance task: 1  available now: 0"),
            (7, equip + " allocated to maintenance task: 1  available now: 0"),
            (7, first + f" starts performing, planned to last for {duration} hours"),
            (end, first + " completed"), (end, first + " frees resources"),
            (end, crew + " deallocated from  maintenance task: 1  available now: 1"),
            (end, equip + " deallocated from  maintenance task: 1  available now: 1"),
        ]
        if serial:
            actions += [(end, second + " started"),
                        (end, second + " requests resources: no resources needed"),
                        (end, second + " starts performing, planned to last for 0.333333 hours"),
                        (7.5, second + " completed")]
        actions += [(7.5, f"system preparation task 0 on {owner} completed"),
                    (7.5, f"{owner} preparation ended, mission: {tag}"),
                    (8, f"{tag} mission starting, duration: 2 : {owner}"),
                    (10, f"{tag} mission success:"), (10, f"{tag} mission completed: {owner}")]
    else:
        actions = [(7.58333, f"{tag} mission cancelled:"),
                   (7.58333, first + " ordered to stop"),
                   (7.58333, first + " resource waiting stopped"),
                   (7.58333, f"system preparation task 0 on {owner} stopped"),
                   (7.58333, f"{owner} preparation ended, mission: {tag}")]
    lines += [f"Time: {hour} {body}" for hour, body in actions]
    return "\n".join(lines)


class C02VersionedTests(unittest.TestCase):
    def test_exact_parent_and_sibling_deltas(self):
        generated = BUILD.build()
        self.assertEqual(set(generated), set(BUILD.VARIANTS))
        parent = json.loads(BUILD.PARENT.read_bytes())
        for variant, (data, diff) in generated.items():
            self.assertEqual(data, (CASE / "inputs" / f"{variant}.json").read_bytes())
            self.assertEqual(diff, (CASE / "parent-diffs" / f"{variant}.json").read_bytes())
            document = json.loads(data)
            expected = BUILD.VARIANTS[variant]
            allocation = BUILD.rows(BUILD.table(document, "ResourceAllocation"))
            self.assertEqual([(row["RID"], row["RQTY"]) for row in allocation],
                             [("P-CREW", 1), ("P-OTHER", 0), ("E-GSE", expected[1])])
            demand = BUILD.rows(BUILD.table(document, "SubTaskResource"))
            self.assertEqual([(row["SEQ"], row["RID"], row["QTY"]) for row in demand],
                             [(1, "P-CREW", 1), (1, "E-GSE", 1)])
            breakdown = BUILD.rows(BUILD.table(document, "TaskBreakDown"))
            self.assertEqual(len(breakdown), 2 if expected[0] else 1)
            record = json.loads(diff)
            self.assertEqual(record["parent_case"], "C01@1.0.2/capacity-2")
            self.assertEqual(record["parent_input_sha256"], BUILD.PARENT_SHA256)
            self.assertEqual(BUILD.rows(BUILD.table(document, "MissionPreparation")),
                             BUILD.rows(BUILD.table(parent, "MissionPreparation")))

    def test_joint_lease_and_no_partial_lease_controls(self):
        for variant, (serial, equipment) in BUILD.VARIANTS.items():
            log = fake_log(serial, equipment == 1)
            report = fake_report(serial, equipment == 1)
            errors, observed = VALIDATE.check_behavior(log, report, variant)
            self.assertEqual(errors, [], variant)
            if equipment == 1:
                lines = log.splitlines()
                lease = next(i for i, line in enumerate(lines) if "E-GSE" in line and " allocated to maintenance task:" in line)
                work = next(i for i, line in enumerate(lines) if " starts performing," in line)
                lines[lease], lines[work] = lines[work], lines[lease]
                self.assertTrue(VALIDATE.check_behavior("\n".join(lines), report, variant)[0])
            else:
                changed = log + "\nTime: 7 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"
                self.assertTrue(VALIDATE.check_behavior(changed, report, variant)[0])


if __name__ == "__main__":
    unittest.main()
