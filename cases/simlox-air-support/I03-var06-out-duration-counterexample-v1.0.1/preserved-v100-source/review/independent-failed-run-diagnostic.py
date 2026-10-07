"""Read-only failure diagnosis of the original sealed v100 child; never accepts it."""
from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
RUN = HERE / "runs/i03-var06-out-dt4-v100-ssh-20261008-01"
PARENT = HERE.parent / "I03-var02-idle-crew-out-v1.0.2/runs/i03-var02-idle-out-v102-ssh-20261007-01"
MANIFEST_SHA = "ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9"
APPROVAL_SHA = "2def8ec3afe09bb632730832fa09267d98d5045b58ec344b4ddfbbd81c67a2ff"
ORIGINAL_REPLAY_SHA = "c3727fff989fff711482371c89298c4f2b147eea6e07f0610406897459979836"


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check(path: Path, entry: dict) -> None:
    assert path.is_file() and seal(path) == {k: entry[k] for k in ("bytes", "sha256")}, str(path)


def doc(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def main() -> None:
    manifest_path = HERE / "prelaunch-manifest.json"
    assert seal(manifest_path)["sha256"] == MANIFEST_SHA
    manifest = doc(manifest_path)
    source_map = {x["key"]: x["sha256"] for x in manifest["source_files"]}
    assert len(source_map) == len(manifest["source_files"]) == 445
    for entry in manifest["source_files"]:
        check(Path(entry["path"]), entry)
    approval_path = HERE / "review/independent-prelaunch-go.json"
    assert seal(approval_path)["sha256"] == APPROVAL_SHA
    assert seal(HERE / "review/independent_replay.py")["sha256"] == ORIGINAL_REPLAY_SHA
    approval = doc(approval_path)
    assert approval["decision"] == "GO_PRELAUNCH" and approval["manifest_sha256"] == MANIFEST_SHA
    assert approval["independent_replay_sha256"] == ORIGINAL_REPLAY_SHA
    assert source_map["child_input"] == approval["input_sha256"]

    invocation = doc(RUN / "invocation.json")
    closure = doc(RUN / "closure.json")
    failure = doc(RUN / "failure-seal.json")
    assert invocation["schema"] == "i03-var06-out-dt4-invocation/v1"
    assert closure["schema"] == "i03-var06-out-dt4-closure/v1"
    assert failure["schema"] == "i03-var06-out-dt4-failure-seal/v1"
    assert {invocation["run_id"], closure["run_id"], failure["run_id"]} == {manifest["run_id"]}
    assert closure["invocation_sha256"] == seal(RUN / "invocation.json")["sha256"]
    assert invocation["approval_sha256"] == closure["approval_sha256"] == APPROVAL_SHA
    assert invocation["manifest_sha256"] == closure["manifest_sha256"] == MANIFEST_SHA
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"] == source_map
    assert closure["error"] == closure["step_error"] == "child OS exit=1"
    raw = closure["raw"]
    assert len(raw) == 23 and set(raw) == {p.name for p in RUN.iterdir() if p.is_file()} - {
        "invocation.json", "closure.json", "failure-seal.json"}
    for name, entry in raw.items():
        assert Path(name).name == name
        check(RUN / name, entry)
    assert len(failure["files"]) == 25
    for name, entry in failure["files"].items():
        check(RUN / name, entry)
    steps = doc(RUN / "steps.json")
    assert [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert [s["exit_code"] for s in steps] == [0, 0, 0, 0, 0, 1]
    assert [s["status"] for s in steps] == ["completed"] * 5 + ["failed"]
    for step in steps:
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        assert type(step["child_session_id"]) is int and step["child_session_id"] == 0
        assert step["capture_error"] is None and step["gui_preserved"] is True
        for kind in ("stdout", "stderr"):
            path = Path(step[kind + "_path"])
            assert path.parent == RUN and path.name in raw
            assert seal(path) == {"bytes": step[kind + "_bytes"], "sha256": step[kind + "_sha256"]}
            assert seal(path) == raw[path.name]
        assert Path(step["stderr_path"]).read_bytes() == b""
    assert doc(RUN / "roundtrip-validation.json")["passed"] is True
    behavior = doc(RUN / "author-validation.json")
    assert behavior["passed"] is False and behavior["error"].startswith("AssertionError: (26,")
    assert "transfer time: 4" in behavior["error"]
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    assert "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log

    # Parse native's trailing-comma report form with the already frozen independent parser.
    source = HERE / "review/independent_replay.py"
    spec = importlib.util.spec_from_file_location("frozen_independent_reader", source)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    for name in ("native-input.json", f"runs/{RUN.name}/roundtrip-raw.json"):
        model = reader.native_json((HERE / name).read_bytes())
        transfer_table = next(t for t in model["model"]["tables"] if t["name"] == "ResourceTransfer")
        cols = [x["name"] for x in transfer_table["columns"]]
        assert len(transfer_table["instances"]) == 1
        transfer_rows = transfer_table["instances"][0]["rows"]
        assert len(transfer_rows) == 1
        transfer_row = transfer_rows[0]
        assert transfer_row[cols.index("STFID")] == "BASE-01"
        assert transfer_row[cols.index("STTID")] == "<OUTSIDE>"
        assert transfer_row[cols.index("RID")] == "P-CREW"
        assert transfer_row[cols.index("TFTIME")] == 6
        assert transfer_row[cols.index("TFQTY")] == 1
        assert type(transfer_row[cols.index("TFDT")]) in (int, float)
        assert transfer_row[cols.index("TFDT")] == 4
    parent_report = reader.native_json((PARENT / "report-raw.json").read_bytes())["report"]["tables"]
    child_report = reader.native_json((RUN / "report-raw.json").read_bytes())["report"]["tables"]
    assert len(parent_report) == len(child_report) == 6
    count, differences = 0, []
    for parent_table, child_table in zip(parent_report, child_report):
        assert parent_table["name"] == child_table["name"]
        assert parent_table["columns"] == child_table["columns"]
        assert len(parent_table["instances"]) == len(child_table["instances"])
        for parent_inst, child_inst in zip(parent_table["instances"], child_table["instances"]):
            assert parent_inst["instance_name"] == child_inst["instance_name"]
            assert len(parent_inst["rows"]) == len(child_inst["rows"])
            for ri, (pr, cr) in enumerate(zip(parent_inst["rows"], child_inst["rows"])):
                assert len(pr) == len(cr) == len(parent_table["columns"])
                for ci, (pv, cv) in enumerate(zip(pr, cr)):
                    count += 1
                    if type(pv) is not type(cv) or pv != cv:
                        differences.append([parent_table["name"], parent_inst["instance_name"], ri,
                                            parent_table["columns"][ci]["name"], pv, cv])
    assert count == 5210 and len(differences) == 1 and differences[0][:4] == ["ProblemDescription", "", 0, "PDESC"]
    resource_total = next(t for t in child_report if t["name"] == "ResourceResultsTotal")
    resource_total_columns = [c["name"] for c in resource_total["columns"]]
    resource_total_row = resource_total["instances"][0]["rows"][0]
    expected_means = {"NR": 1.1666666269302368, "NRA": 1.1666666269302368,
                      "NRN": 1.1666666269302368, "NRUM": 0.0555555559694767,
                      "NRW": 0.02777777798473835}
    for field, expected in expected_means.items():
        assert type(resource_total_row[resource_total_columns.index(field)]) is float
        assert resource_total_row[resource_total_columns.index(field)] == expected

    parent_lines = (PARENT / "model.log").read_text(encoding="utf-8-sig").splitlines()
    child_lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    assert len(parent_lines) == len(child_lines) == 240
    changed = []
    for tag, i, j, k, l in difflib.SequenceMatcher(None, parent_lines, child_lines, autojunk=False).get_opcodes():
        if tag != "equal":
            changed.append([tag, i + 1, j, k + 1, l, parent_lines[i:j], child_lines[k:l]])
    assert len(changed) == 2
    assert parent_lines[25].endswith("transfer time: 0") and child_lines[25].endswith("transfer time: 4")
    assert parent_lines[26] == "Time: 6  resource transfer task 0 (OUT)  arrives with 1 resources"
    assert child_lines[129] == "Time: 10  resource transfer task 0 (OUT)  arrives with 1 resources"

    # Original independent v100 reader fails before its physical gate. It cannot be retroactively accepted.
    replay_error = (HERE / "review/independent-postrun-failed.stderr.bin").read_text(encoding="utf-8")
    assert "KeyError: 'owned_exact_archive'" in replay_error
    assert (HERE / "review/independent-postrun-failed.stdout.bin").read_bytes() == b""
    result = {"schema": "i03-var06-independent-failed-run-diagnostic/v1", "decision": "NO_GO_RUN",
              "manifest_sha256": MANIFEST_SHA, "approval_sha256": APPROVAL_SHA,
              "run_id": manifest["run_id"], "source_records": 445, "raw_records": 23,
              "failure_seal_files": 25, "step_exit_codes": [s["exit_code"] for s in steps],
              "parent_log_lines": 240, "child_log_lines": 240, "log_changes": changed,
              "report_cells_compared": count, "report_differences": differences,
              "five_exact_resource_total_means": expected_means,
              "exported_out_tfdt": 4,
              "original_independent_reader_failure": "missing contract owned_exact_archive key before physical gate"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
