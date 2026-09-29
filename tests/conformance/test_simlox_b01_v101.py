"""Focused B01 1.0.1 source and observable-behavior regression checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/B01-fixed-preparation-v1.0.1"
sys.path.insert(0, str(CASE))
for name in ("build", "validate"):
    spec = importlib.util.spec_from_file_location(name, CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
BUILD, VALIDATE = sys.modules["build"], sys.modules["validate"]


def sample_events() -> str:
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    owner = "<TEACH-AIR-01,0>"
    return "\n".join(f"Time: {hour} {body}" for hour, body in [
        (7, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (7, f"{tag} mission created:"),
        (7, f"{tag} mission allocates system: {owner}"),
        (7, f"{owner} preparation started, mission: {tag}"),
        (7, f"system preparation task 0 on {owner} started"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} started"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} requests resources: no resources needed"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} resource availability test"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} starts performing, planned to last for 0.5 hours"),
        (7.5, f"subtask 0 seqno 0 within system preparation task 0 on {owner} completed"),
        (7.5, f"system preparation task 0 on {owner} completed"),
        (7.5, f"{owner} preparation ended, mission: {tag}"),
        (8, f"{tag} mission starting, duration: 2 : {owner}"),
        (10, f"{tag} mission success:"),
        (10, f"{tag} mission completed: {owner}"),
    ])


def sample_report() -> dict:
    names = ["UNID", "SID", "STINT", "ETINT", "NSYA", "NPSTA", "NPSUC", "NSYMP", "FTMO", "NSYMO"]
    rows = []
    for index in range(72):
        start = index / 2
        rows.append(["Total over all Units", "Total over all Systems", start, start + 0.5, 1,
                     int(start == 7), int(start == 7.5), int(start == 7),
                     int(8 <= start < 10), int(8 <= start < 10)])
    return {"report": {"tables": [
        {"name": "ResultSummary", "columns": [{"name": value} for value in ("NREP", "RTILW", "RTIUP", "MSTF", "MSUF")],
         "instances": [{"rows": [[1, 0, 36, 1, 1]]}]},
        {"name": "SystemResults", "columns": [{"name": value} for value in names],
         "instances": [{"rows": rows}]},
    ]}}


class B01VersionedSourceTests(unittest.TestCase):
    def test_exact_two_row_delta_and_stable_parent_identities(self):
        candidate, diff = BUILD.build()
        self.assertEqual(candidate, (CASE / "native-input.json").read_bytes())
        self.assertEqual(diff, (CASE / "parent-diff.json").read_bytes())
        record = json.loads(diff)
        self.assertEqual(record["changed_tables_only"], ["MissionPreparation", "Tasks"])
        self.assertEqual(record["added_rows"], 2)
        self.assertEqual(record["removed_rows"], 0)
        self.assertEqual(record["field_changes"], 0)
        parent = json.loads(BUILD.PARENT.read_bytes())
        child = json.loads(candidate)
        for name in ("System", "SystemDeployment", "MissionType", "OperationProfile", "Control", "Unit"):
            self.assertEqual(BUILD.table(parent, name), BUILD.table(child, name))
        self.assertEqual(BUILD.rows(BUILD.table(child, "MissionPreparation")), [BUILD.PREPARATION])
        self.assertEqual(BUILD.rows(BUILD.table(child, "Tasks")), [BUILD.TASK])

    def test_observable_lifecycle_rejects_extra_or_wrong_owner(self):
        events = sample_events()
        self.assertEqual(VALIDATE.check_events(events), [])
        self.assertTrue(VALIDATE.check_events(events + "\nTime: 11 <TEACH-AIR-01,0> preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"))
        self.assertTrue(VALIDATE.check_events(events.replace("<TEACH-AIR-01,0> preparation ended", "<OTHER-AIR,0> preparation ended")))
        self.assertTrue(VALIDATE.check_events(events.replace("duration: 2", "duration: 1")))

    def test_report_checks_full_horizon_and_completion_count(self):
        report = sample_report()
        self.assertEqual(VALIDATE.check_report(report), [])
        system_rows = report["report"]["tables"][1]["instances"][0]["rows"]
        system_rows[15][6] = 0  # NPSUC missing in 07:30-08:00 window
        self.assertTrue(VALIDATE.check_report(report))
        system_rows[15][6] = 1
        system_rows[30][5] = 1  # extra off-time preparation start
        self.assertTrue(VALIDATE.check_report(report))


if __name__ == "__main__":
    unittest.main()
