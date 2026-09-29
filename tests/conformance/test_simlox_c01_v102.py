"""C01 four-variant source and resource-gating negative controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/C01-personnel-capacity-v1.0.2"
sys.path.insert(0, str(CASE))
for name in ("build", "validate"):
    spec = importlib.util.spec_from_file_location(f"c01_{name}", CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"c01_{name}"] = module
    if name == "build":
        sys.modules["build"] = module
    spec.loader.exec_module(module)
BUILD, VALIDATE = sys.modules["c01_build"], sys.modules["c01_validate"]


def positive_log() -> str:
    tag, owner = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<TEACH-AIR-01,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    rows = [
        (7, "<TEACH-UNIT> mission ordered: BASIC-MISSION"), (7, f"{tag} mission created:"),
        (7, f"{tag} mission allocates system: {owner}"),
        (7, f"{owner} preparation started, mission: {tag}"),
        (7, f"system preparation task 0 on {owner} started"),
        (7, first + " started"), (7, first + " requests resources"),
        (7, first + " resource availability test"),
        (7, first + " books resources"),
        (7, "<P-CREW at <BASE-01,0>> allocated to maintenance task: 2  available now: 0"),
        (7, first + " starts performing, planned to last for 0.166667 hours"),
        (7.16667, first + " completed"), (7.16667, first + " frees resources"),
        (7.16667, "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 2  available now: 2"),
        (7.16667, second + " started"),
        (7.16667, second + " requests resources: no resources needed"),
        (7.16667, second + " resource availability test"),
        (7.16667, second + " starts performing, planned to last for 0.333333 hours"),
        (7.5, second + " completed"), (7.5, f"system preparation task 0 on {owner} completed"),
        (7.5, f"{owner} preparation ended, mission: {tag}"),
        (8, f"{tag} mission starting, duration: 2 : {owner}"),
        (10, f"{tag} mission success:"), (10, f"{tag} mission completed: {owner}"),
    ]
    lines = [f"Time: {hour} {body}" for hour, body in rows]
    lines.insert(8, "  Availability test on  <P-CREW at <BASE-01,0>> request for: 2 OK")
    return "\n".join(lines)


class C01VersionedTests(unittest.TestCase):
    def test_four_exact_parent_deltas_and_sibling_capacity_only(self):
        built = BUILD.build()
        self.assertEqual(set(built), set(BUILD.VARIANTS))
        reference = None
        for variant, (native, diff) in built.items():
            self.assertEqual(native, (CASE / "inputs" / f"{variant}.json").read_bytes())
            self.assertEqual(diff, (CASE / "parent-diffs" / f"{variant}.json").read_bytes())
            record = json.loads(diff)
            self.assertEqual((record["added_rows"], record["removed_rows"], record["field_changes"]), (5, 0, 0))
            self.assertEqual(record["changed_tables_only"], list(BUILD.CHANGED_TABLES))
            document = json.loads(native)
            allocation = BUILD.rows(BUILD.table(document, "ResourceAllocation"))
            self.assertEqual([row["RQTY"] for row in allocation], list(BUILD.VARIANTS[variant]))
            tables = {t["name"]: t for t in document["model"]["tables"] if t["name"] != "ResourceAllocation"}
            if reference is None:
                reference = tables
            else:
                self.assertEqual(tables, reference)
        with self.assertRaises(ValueError):
            BUILD.build_variant(json.loads(BUILD.PARENT.read_bytes()), "unlisted")

    def test_positive_lease_and_wrong_or_partial_lease_controls(self):
        log = positive_log()
        errors, observed = VALIDATE.check_events(log, "capacity-2")
        self.assertEqual(errors, [])
        self.assertEqual(observed["lease_person_minutes"], 20)
        mutations = [log.replace("request for: 2 OK", "request for: 1 OK"),
                     log.replace("allocated to maintenance task: 2", "allocated to maintenance task: 1"),
                     log.replace("<P-CREW at", "<P-OTHER at"),
                     log.replace("Time: 7.16667 subtask 1", "Time: 7 subtask 1"),
                     log.replace("0.333333 hours", "0.75 hours")]
        lines = log.splitlines()
        acquire = next(i for i, row in enumerate(lines) if " allocated to maintenance task:" in row)
        work = next(i for i, row in enumerate(lines) if " starts performing, planned to last for 0.166667" in row)
        lines[acquire], lines[work] = lines[work], lines[acquire]
        mutations.append("\n".join(lines))
        for changed in mutations:
            with self.subTest(change=changed[-100:]):
                self.assertTrue(VALIDATE.check_events(changed, "capacity-2")[0])


if __name__ == "__main__":
    unittest.main()
