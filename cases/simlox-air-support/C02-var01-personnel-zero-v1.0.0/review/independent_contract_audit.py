"""Read-only byte and source audit for the frozen C02.var01 contract."""

import hashlib
import json
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
CONTRACT = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
BASE = CONTRACT["ownership"]["base_commit"]
CHECKS = 0
FAILURES = []


def check(condition, label):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(label)


def seal(data, expected, label):
    check(len(data) == expected["bytes"], label + " size")
    check(hashlib.sha256(data).hexdigest() == expected["sha256"], label + " SHA256")


def disk(path, expected, label):
    try:
        seal(Path(path).read_bytes(), expected, label)
    except OSError as exc:
        check(False, label + f" read: {exc}")


def git(path, expected, label):
    result = subprocess.run(
        ["git", "show", f"{BASE}:{path}"], cwd=ROOT, capture_output=True
    )
    check(result.returncode == 0, label + " Git blob present")
    if result.returncode == 0:
        seal(result.stdout, expected, label + " Git blob")


def relative(record, label):
    disk(ROOT / record["path"], record, label)


def published_sources(package_name, records, label):
    for row in records:
        rel = f"cases/simlox-air-support/{package_name}/{row['path']}"
        disk(ROOT / rel, row["local_disk"], label + " local " + row["path"])
        git(rel, row["published_git"], label + " published " + row["path"])


def run(run_record, label):
    base = Path(run_record["local_run_dir"])
    check(base.name == run_record["run_id"], label + " run directory identity")
    for name in ("invocation", "closure"):
        row = run_record[name]
        disk(base / row.get("path", f"{name}.json"), row, label + " " + name)
    for name, row in run_record["raw"].items():
        disk(base / name, row, label + " raw " + name)
    check(len(run_record["raw"]) == 11, label + " eleven raw files")


def tables(path):
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def row(table, **keys):
    columns = [c["name"] for c in table["columns"]]
    matches = [dict(zip(columns, r)) for r in table["instances"][0]["rows"]]
    selected = [r for r in matches if all(r[k] == v for k, v in keys.items())]
    check(len(selected) == 1, f"unique {table['name']} row {keys}")
    return selected[0] if len(selected) == 1 else {}


def main():
    check(CONTRACT["case_id"] == "C02" and CONTRACT["variant_id"] == "C02.var01", "case identity")
    check(CONTRACT["version"] == "1.0.0", "version")
    check(BASE == "1a80bbe5bcfb0351f27c55c7e0cf665bc761e4c6", "base commit")
    check(not (PACKAGE / "native-input.json").exists(), "no child input")
    check(not (PACKAGE / "runs").exists(), "no child runs")
    own = CONTRACT["ownership"]
    relative(own["root_selection_context"], "owner selection")
    check(own["sole_new_run_id"] == "c02-var01-v100-personnel0-ssh-20261007-01", "unique run ID")
    for name in ("exe", "manual", "dictionary"):
        rec = CONTRACT["installed"][name]
        disk(rec["path"], rec, "installed " + name)
    catalog = CONTRACT["catalog"]
    relative(catalog["publication_index_at_selection"], "publication snapshot")
    pubs = json.loads((ROOT / catalog["publication_index_at_selection"]["path"]).read_text(encoding="utf-8"))
    check(len(pubs["entries"]) == 487, "487 preceding publications")
    for publication_id, package, evidence in (
        ("B01.fixed_prep.1.0.1", "B01-fixed-preparation-v1.0.1", "evidence-2026-09-29.md"),
        ("B02.serial_prep.1.0.2", "B02-serial-preparation-v1.0.2", "evidence-2026-09-29.md"),
        ("C01.personnel.1.0.2", "C01-personnel-capacity-v1.0.2", "evidence-2026-09-29.md"),
        ("C02.joint_resources.1.0.2", "C02-joint-resources-v1.0.2", "evidence-2026-09-29.md"),
    ):
        matching = [e for e in pubs["entries"] if e.get("publication_id") == publication_id]
        check(len(matching) == 1, publication_id + " published once")
        if len(matching) == 1:
            check(matching[0]["package"] == package and matching[0]["evidence"] == f"{package}/{evidence}", publication_id + " links")
    accepted = CONTRACT["accepted_evidence"]
    classification = accepted["classification"]
    relative(classification["evidence_index"], "C02.var03 index")
    relative(classification["signoff"], "C02.var03 signoff")
    for rec in classification["source_files"]:
        rel = f"cases/simlox-air-support/{classification['package']}/{rec['path']}"
        disk(ROOT / rel, rec, "C02.var03 " + rec["path"])
        git(rel, rec, "C02.var03 " + rec["path"])
    parent = accepted["C02_parent"]
    published_sources(parent["package"], parent["source_files_dual_local_and_git"], "C02")
    relative(parent["evidence_report"], "C02 evidence")
    for run_record in parent["accepted_runs"]:
        run(run_record, "C02 " + run_record["run_id"])
    check(len(parent["accepted_runs"]) == 4, "four C02 accepted runs")
    c01 = accepted["C01_capacity_zero_context"]
    for name, rec in c01["source_files_dual_local_and_git"].items():
        rel = f"cases/simlox-air-support/{c01['package']}/{name}"
        disk(ROOT / rel, {"bytes": rec["local_bytes"], "sha256": rec["local_sha256"]}, "C01 local " + name)
        git(rel, {"bytes": rec["published_git_bytes"], "sha256": rec["published_git_sha256"]}, "C01 Git " + name)
    relative(c01["evidence_report"], "C01 evidence")
    relative(c01["source_input"], "C01 zero input")
    run(c01, "C01 zero")
    for parent_id in ("B02", "B01"):
        relative(accepted["ancestry"][parent_id]["evidence"], parent_id + " evidence")
    source = CONTRACT["source_design"]
    relative(source["parent_input"], "sole input parent")
    model = tables(ROOT / source["parent_input"]["path"])
    check(len(model) == 31, "31 authored tables")
    check(sum(bool(t["instances"][0]["rows"]) for t in model.values()) == 20, "20 row-containing tables")
    a = row(model["ResourceAllocation"], POINT="AIR_BASIC", RID="P-CREW", STID="BASE-01")
    b = row(model["ResourceAllocation"], POINT="AIR_BASIC", RID="E-GSE", STID="BASE-01")
    check(a.get("RQTY") == 1 and b.get("RQTY") == 1, "parent crew/device capacity")
    r1 = row(model["SubTaskResource"], TID="PREP-FIXED", SEQ=1, RID="P-CREW")
    r2 = row(model["SubTaskResource"], TID="PREP-FIXED", SEQ=1, RID="E-GSE")
    check(r1.get("QTY") == r2.get("QTY") == 1 and r1.get("RPROB") == r2.get("RPROB") == 1, "joint certain subtask request")
    check(not model["TaskResource"]["instances"][0]["rows"], "no main task resource")
    check(not model["ResourceRemoteSupport"]["instances"][0]["rows"] if "ResourceRemoteSupport" in model else True, "no remote resource support")
    op = row(model["OperationProfile"], PRID="BASIC-SCHEDULE", SPRID="BASIC-MISSION")
    mt = row(model["MissionType"], MTID="BASIC-MISSION")
    check(op.get("STIM") == 8 and op.get("DTIM") == 1/3 and mt.get("NOPER") == 1, "notice/deferment profile")
    check(abs(source["common_physical"]["latest_launch_hour"] - (op["STIM"] + op["DTIM"])) < 1e-14, "latest launch arithmetic")
    check(len(source["sole_child_delta"]) == 2, "two declared changes")
    check(source["sole_child_delta"][0]["before"] == 1 and source["sole_child_delta"][0]["after"] == 0, "crew 1 to 0")
    print(json.dumps({"checks": CHECKS, "failures": FAILURES, "decision": "PASS" if not FAILURES else "FAIL"}, sort_keys=True))


if __name__ == "__main__":
    main()
