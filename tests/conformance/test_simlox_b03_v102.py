"""B03 source lineage and recipe separation negative controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/B03-explicit-cold-hot-v1.0.2"
sys.path.insert(0, str(CASE))
for name in ("build", "validate"):
    spec = importlib.util.spec_from_file_location(f"b03_{name}", CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"b03_{name}"] = module
    if name == "build":
        sys.modules["build"] = module
    spec.loader.exec_module(module)
BUILD = sys.modules["b03_build"]
VALIDATE = sys.modules["b03_validate"]


def example_log() -> str:
    owner = "<TEACH-AIR-01,0>"
    entries = []
    subtask_index = 0
    for task_index, (mtid, notice, launch, ordinal, minutes) in enumerate((
        ("COLD-FIRST", 7, 8, 0, (10, 20)),
        ("HOT-SORTIE", 11, 12, 1, (10,)),
        ("HOT-SORTIE", 15, 16, 2, (10,)),
    )):
        tag = f"<{mtid},TEACH-UNIT,0,0,{ordinal}>"
        entries.extend([(notice, f"<TEACH-UNIT> mission ordered: {mtid}"),
                        (notice, f"{tag} mission created:"),
                        (notice, f"{tag} mission allocates system: {owner}"),
                        (notice, f"{owner} preparation started, mission: {tag}"),
                        (notice, f"system preparation task {task_index} on {owner} started")])
        elapsed = 0
        for seq, duration in enumerate(minutes, 1):
            start = notice + elapsed / 60
            prefix = f"subtask {subtask_index} seqno {seq} within system preparation task {task_index} on {owner}"
            entries.extend([(start, prefix + " started"),
                            (start, prefix + " requests resources: no resources needed"),
                            (start, prefix + " resource availability test"),
                            (start, prefix + f" starts performing, planned to last for {duration/60:.6f} hours")])
            elapsed += duration
            entries.append((notice + elapsed / 60, prefix + " completed"))
            subtask_index += 1
        finish = notice + elapsed / 60
        entries.extend([(finish, f"system preparation task {task_index} on {owner} completed"),
                        (finish, f"{owner} preparation ended, mission: {tag}"),
                        (launch, f"{tag} mission starting, duration: 2 : {owner}"),
                        (launch + 2, f"{tag} mission success:"),
                        (launch + 2, f"{tag} mission completed: {owner}")])
    return "\n".join(f"Time: {hour:.6f} {body}" for hour, body in entries)


class B03VersionedTests(unittest.TestCase):
    def test_exact_parent_lineage_and_business_ids(self):
        candidate, diff = BUILD.build()
        self.assertEqual(candidate, (CASE / "native-input.json").read_bytes())
        self.assertEqual(diff, (CASE / "parent-diff.json").read_bytes())
        record = json.loads(diff)
        self.assertEqual(record["parent_case"], "B02@1.0.2")
        self.assertEqual(record["changed_tables_only"], list(BUILD.CHANGED_TABLES))
        parent, child = json.loads(BUILD.PARENT.read_bytes()), json.loads(candidate)
        for name in ("System", "SystemDeployment", "Control", "Unit", "ResultCollection"):
            self.assertEqual(BUILD.table(parent, name), BUILD.table(child, name))
        self.assertEqual([r["STIM"] for r in BUILD.rows(BUILD.table(child, "OperationProfile"))], [8, 12, 16])
        self.assertEqual([r["TID"] for r in BUILD.rows(BUILD.table(child, "MissionPreparation"))],
                         ["PREP-FIXED", "HOT-PREP"])

    def test_event_binding_and_negative_controls(self):
        log = example_log()
        self.assertEqual(VALIDATE.check_events(log), [])
        variants = [
            log.replace("mission ordered: COLD-FIRST", "mission ordered: HOT-SORTIE", 1),
            log.replace("subtask 1 seqno 2", "subtask 1 seqno 1", 1),
            log.replace("0.333333 hours", "0.166667 hours", 1),
            log.replace("Time: 8.000000 <COLD-FIRST", "Time: 7.250000 <COLD-FIRST", 1),
            log.replace("Time: 11.166667 subtask 2", "Time: 11.000000 subtask 2", 1),
            log.replace("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>", 1),
            log + "\nTime: 19.000000 subtask 4 seqno 1 within system preparation task 3 on <TEACH-AIR-01,0> started",
        ]
        for changed in variants:
            with self.subTest(change=changed[-110:]):
                self.assertTrue(VALIDATE.check_events(changed))


if __name__ == "__main__":
    unittest.main()
