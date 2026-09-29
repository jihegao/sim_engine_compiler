"""C03 exact-parent, shared-capacity, and owner-lease controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "cases/simlox-air-support/C03-shared-crew-formation-v1.0.2"
sys.path.insert(0, str(CASE))
for name in ("build", "validate"):
    spec = importlib.util.spec_from_file_location(f"c03_{name}", CASE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"c03_{name}"] = module
    if name == "build":
        sys.modules["build"] = module
    spec.loader.exec_module(module)
BUILD, VALIDATE = sys.modules["c03_build"], sys.modules["c03_validate"]

RUNS = {"staffing-2": "c03-v102-staff2-ssh-20260929-04",
        "staffing-1": "c03-v102-staff1-ssh-20260929-02",
        "staffing-0": "c03-v102-staff0-ssh-20260929-02"}


class C03VersionedTests(unittest.TestCase):
    def test_exact_parent_and_capacity_only_sibling_delta(self):
        parent = json.loads(BUILD.PARENT.read_bytes())
        children = {}
        for variant, capacity in BUILD.CAPACITIES.items():
            model, diff = BUILD.build_variant(parent, variant)
            self.assertEqual(model, (CASE / "inputs" / f"{variant}.json").read_bytes())
            self.assertEqual(diff, (CASE / "parent-diffs" / f"{variant}.json").read_bytes())
            child = json.loads(model)
            children[variant] = child
            self.assertEqual(BUILD.rows(BUILD.table(child, "SystemDeployment"))[0]["QTYPS"], 2)
            self.assertEqual(BUILD.rows(BUILD.table(child, "MissionType"))[0]["NOS"], 2)
            self.assertEqual(BUILD.rows(BUILD.table(child, "MissionType"))[0]["MNOS"], 2)
            self.assertEqual([(row["RID"], row["RQTY"]) for row in
                              BUILD.rows(BUILD.table(child, "ResourceAllocation"))],
                             [("P-CREW", capacity)])
            self.assertEqual([(row["RID"], row["QTY"]) for row in
                              BUILD.rows(BUILD.table(child, "SubTaskResource"))],
                             [("P-CREW", 1)])
        baseline = children["staffing-2"]
        for variant in ("staffing-1", "staffing-0"):
            child = children[variant]
            for old, new in zip(baseline["model"]["tables"], child["model"]["tables"], strict=True):
                if old["name"] != "ResourceAllocation":
                    self.assertEqual(old, new, f"{variant} changed {old['name']}")

    def test_native_owner_lease_order_and_blocked_control(self):
        base = CASE / "runs"
        if not all((base / run / "model.log").is_file() for run in RUNS.values()):
            self.skipTest("sealed local SIMLOX raw runs are not checked into Git")
        for variant, run_id in RUNS.items():
            run = base / run_id
            report = VALIDATE.load(run / "report-raw.json")
            log = (run / "model.log").read_text(encoding="utf-8-sig")
            self.assertEqual(VALIDATE.check_behavior(log, report, variant)[0], [], variant)
        run = base / RUNS["staffing-1"]
        report = VALIDATE.load(run / "report-raw.json")
        lines = (run / "model.log").read_text(encoding="utf-8-sig").splitlines()
        lease = next(i for i, line in enumerate(lines) if " allocated to maintenance task:" in line)
        work = next(i for i, line in enumerate(lines) if " starts performing," in line)
        lines[lease], lines[work] = lines[work], lines[lease]
        self.assertTrue(VALIDATE.check_behavior("\n".join(lines), report, "staffing-1")[0])
        run = base / RUNS["staffing-0"]
        report = VALIDATE.load(run / "report-raw.json")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        phantom = "\nTime: 7.5 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"
        self.assertTrue(VALIDATE.check_behavior(log + phantom, report, "staffing-0")[0])


if __name__ == "__main__":
    unittest.main()
