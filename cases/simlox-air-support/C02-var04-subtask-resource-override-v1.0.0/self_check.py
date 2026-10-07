"""Read-only synthetic checks of source, typed event and full-cell rejection gates."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

import build
import check_roundtrip
import validate_native_cli as validator


def clean(g: validator.Gate) -> None:
    assert not g.failures, g.failures[:8]


def check() -> None:
    build.main()
    parent = json.loads(build.PARENT.read_bytes())
    joint = build.build(parent, "joint")
    crew = build.build(parent, "crewonly")
    assert [t["name"] for t in joint["model"]["tables"]] == [t["name"] for t in parent["model"]["tables"]]
    assert len(build.diff(joint, crew)) == 10
    damaged = copy.deepcopy(crew)
    build.table(damaged, "Station")["rows"][0][0] = "DRIFT"
    assert build.diff(crew, damaged), "source cell mutation escaped"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        (path / "input.json").write_bytes((build.HERE / "joint-input.json").read_bytes())
        (path / "roundtrip-raw.json").write_bytes((build.HERE / "joint-input.json").read_bytes())
        (path / "import.log").write_text("Import completed!", encoding="utf-8")
        (path / "export.log").write_text("Export completed!", encoding="utf-8")
        assert check_roundtrip.check(path, "joint")["passed"]
        for mutation in ("column", "instance", "row", "metadata"):
            changed = copy.deepcopy(joint)
            if mutation == "column":
                next(t for t in changed["model"]["tables"] if t["name"] == "TaskResource")["columns"][0]["datatype"] = "integer"
            elif mutation == "instance":
                build.table(changed, "TaskResource")["instance_name"] = "DRIFT"
            elif mutation == "row":
                build.table(changed, "TaskResource")["rows"][0][2] = 2
            else:
                changed["model"]["database_version"] = -1
            (path / "roundtrip-raw.json").write_text(json.dumps(changed), encoding="utf-8")
            assert not check_roundtrip.check(path, "joint")["passed"], f"roundtrip {mutation} mutation escaped"
    for arm, accepted in (("joint", validator.ZERO), ("crewonly", validator.BOTH)):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            source_log = (accepted / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            if arm == "crewonly":
                source_log = "\n".join(line for line in source_log.splitlines()
                                       if not ("Availability test on  <E-GSE" in line or
                                               "<E-GSE at <BASE-01,0>> allocated to maintenance task" in line or
                                               "<E-GSE at <BASE-01,0>> deallocated from  maintenance task" in line))
            (path / "model.log").write_text(source_log, encoding="utf-8")
            g = validator.Gate()
            validator.events(g, path / "model.log", arm)
            clean(g)
            if arm == "crewonly":
                wrapped = source_log.replace("planned to last for 0.5 hours",
                                             "planned to last for \n0.5 hours")
                (path / "model.log").write_text(wrapped, encoding="utf-8")
                g = validator.Gate()
                validator.events(g, path / "model.log", arm)
                clean(g)
            bad = source_log.replace("request for: 1 OK", "request for: 2 OK", 1)
            (path / "model.log").write_text(bad, encoding="utf-8")
            g = validator.Gate()
            validator.events(g, path / "model.log", arm)
            assert g.failures, "typed request mutation escaped"
            report = validator.parse(accepted / "report-raw.json")
            tables = {t["name"]: t for t in report["report"]["tables"]}
            tables["ProblemDescription"]["instances"][0]["rows"][0][0] = build.DESCRIPTIONS[arm]
            if arm == "crewonly":
                for name in ("ResourceResults", "ResourceResultsTotal"):
                    t = tables[name]
                    cols = [c["name"] for c in t["columns"]]
                    for row in t["instances"][0]["rows"]:
                        for col in ("NR", "NRA", "NRN"):
                            row[cols.index(col)] = 1
                        row[cols.index("NRUM")] /= 2
            (path / "report-raw.json").write_text(json.dumps(report), encoding="utf-8")
            g = validator.Gate()
            validator.check_report(g, path / "report-raw.json", arm)
            clean(g)
            system = tables["SystemResults"]["instances"][0]["rows"]
            system[25][4] = 98765
            (path / "report-raw.json").write_text(json.dumps(report), encoding="utf-8")
            g = validator.Gate()
            validator.check_report(g, path / "report-raw.json", arm)
            assert g.failures, "unlisted system cell mutation escaped"
    print("source, typed request, and full report mutation checks passed")


if __name__ == "__main__":
    check()
