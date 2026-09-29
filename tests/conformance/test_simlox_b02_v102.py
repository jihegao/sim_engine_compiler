"""Focused B02 source, serial-event and negative-control regression checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/B02-serial-preparation-v1.0.2"
sys.path.insert(0, str(CASE))
for name in ("build", "validate", "review_readonly"):
    spec = importlib.util.spec_from_file_location(f"b02_{name}", CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"b02_{name}"] = module
    if name == "build":
        sys.modules["build"] = module
    spec.loader.exec_module(module)
BUILD = sys.modules["b02_build"]
VALIDATE = sys.modules["b02_validate"]
REVIEW = sys.modules["b02_review_readonly"]


def sample_events() -> str:
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    owner = "<TEACH-AIR-01,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    entries = [
        (7, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (7, f"{tag} mission created:"),
        (7, f"{tag} mission allocates system: {owner}"),
        (7, f"{owner} preparation started, mission: {tag}"),
        (7, f"system preparation task 0 on {owner} started"),
        (7, first + " started"),
        (7, first + " requests resources: no resources needed"),
        (7, first + " resource availability test"),
        (7, first + " starts performing, planned to last for 0.166667 hours"),
        (7.16667, first + " completed"),
        (7.16667, second + " started"),
        (7.16667, second + " requests resources: no resources needed"),
        (7.16667, second + " resource availability test"),
        (7.16667, second + " starts performing, planned to last for 0.333333 hours"),
        (7.5, second + " completed"),
        (7.5, f"system preparation task 0 on {owner} completed"),
        (7.5, f"{owner} preparation ended, mission: {tag}"),
        (8, f"{tag} mission starting, duration: 2 : {owner}"),
        (10, f"{tag} mission success:"),
        (10, f"{tag} mission completed: {owner}"),
    ]
    return "\n".join(f"Time: {hour} {body}" for hour, body in entries)


class B02VersionedTests(unittest.TestCase):
    def test_exact_parent_delta_and_independent_source_review(self):
        candidate, diff = BUILD.build()
        self.assertEqual(candidate, (CASE / "native-input.json").read_bytes())
        self.assertEqual(diff, (CASE / "parent-diff.json").read_bytes())
        record = json.loads(diff)
        self.assertEqual(record["parent_case"], "B01@1.0.1")
        self.assertEqual(record["changed_tables_only"], ["MissionPreparation", "Tasks", "SubTaskType", "TaskBreakDown"])
        self.assertEqual((record["added_rows"], record["removed_rows"], record["field_changes"]), (4, 0, 2))
        self.assertEqual(REVIEW.check_source(), [])
        parent, child = json.loads(BUILD.PARENT.read_bytes()), json.loads(candidate)
        for name in ("System", "SystemDeployment", "MissionType", "OperationProfile", "Control", "Unit"):
            self.assertEqual(BUILD.table(parent, name), BUILD.table(child, name))

    def test_rejects_wrong_step_configurations(self):
        for bad in (((2, "INSPECT", 10), (1, "SERVICE", 20)),
                    ((1, "INSPECT", 0), (2, "SERVICE", 20)),
                    ((1, "INSPECT", 10), (2, "SERVICE", 45)),
                    ((1, "INSPECT", 10), (2, "OTHER", 20))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                BUILD.validate_steps(bad)

    def test_serial_event_observation_and_negative_controls(self):
        events = sample_events()
        self.assertEqual(VALIDATE.check_events(events), [])
        mutations = [
            events.replace("seqno 2", "seqno 1"),
            events.replace("Time: 7.16667 subtask 1", "Time: 7 subtask 1"),
            events.replace("0.333333 hours", "0.75 hours"),
            events.replace("subtask 1 seqno 2", "subtask 2 seqno 2"),
            events.replace("Time: 7.5 <TEACH-AIR-01,0> preparation ended", "Time: 7.75 <TEACH-AIR-01,0> preparation ended"),
            events + "\nTime: 11 subtask 2 seqno 3 within system preparation task 0 on <TEACH-AIR-01,0> started",
        ]
        for changed in mutations:
            with self.subTest(changed=changed[-120:]):
                self.assertTrue(VALIDATE.check_events(changed))


if __name__ == "__main__":
    unittest.main()
