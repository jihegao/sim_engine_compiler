"""Seal D03.var01 sources, accepted parent/child raw, and excluded prelaunch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "D03-var01-single-pm-cycle-v0.1.0"
OUTPUT = HERE / "evidence-index.json"
PARENT = ROOT / "D03-calendar-pm-v1.0.0" / "runs" / "d03-calendar-v100-ssh-20261001-02"
CHILD = HERE / "runs" / "d03-var01-onecycle-v011-ssh-20261006-01"
PARENT_CLOSURE_SHA = "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8"
CHILD_CLOSURE_SHA = "6622cabcb7254b906c9009cb6091fb8a9adc97fef1c7f5f36fbca1c48a476ee2"
NO_GO_SHA = "a19f508c055ac943d497d54651e18ec0950edeb5cdadcac1bfafcaa5cc44eb42"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files(package):
    excluded = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
                "independent-publication-review-2026-10-06.md"}
    return [{"path": p.relative_to(package).as_posix(), "bytes": p.stat().st_size,
             "sha256": sha(p)}
            for p in sorted(package.rglob("*"))
            if p.is_file() and p.name not in excluded and "runs" not in p.parts
            and "__pycache__" not in p.parts and p.suffix != ".pyc"]


def sealed_run(role, path, closure_sha):
    cp, ip = path / "closure.json", path / "invocation.json"
    assert sha(cp) == closure_sha
    closure = load(cp)
    assert closure["run_id"] == path.name and closure["invocation_sha256"] == sha(ip)
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        raw = path / name
        assert raw.is_file() and raw.stat().st_size == seal["bytes"] and sha(raw) == seal["sha256"], raw
    return {"role": role, "run_id": path.name, "local_run_dir": str(path.resolve()),
            "invocation": {"bytes": ip.stat().st_size, "sha256": sha(ip)},
            "closure": {"bytes": cp.stat().st_size, "sha256": closure_sha}, "raw": closure["raw"]}


def main():
    assert sha(OLD / "review" / "independent-prelaunch-no-go-2026-10-06.md") == NO_GO_SHA
    assert not (OLD / "runs" / "d03-var01-onecycle-v010-ssh-20261006-01").exists()
    assert sha(HERE / "contract.json") == "ec40614d1b6c916a7108e3c07b35ac7d0ea035f6d24a5d2ae32f6f4ec231c107"
    assert sha(HERE / "native-input.json") == "760cb41baca99d7fe3b8558a58c7330acb81944bb3d3ceba4e4241c06b9b9a00"
    assert sha(HERE / "review" / "independent-prelaunch-go-2026-10-06.md") == "457655897d033b0d5d9e9cff4f210161cc26051abce8dbcbf3e7e7201dfa8faa"
    assert sha(HERE / "review" / "author-native-validation-2026-10-06.json") == "7b77cb64f02121e0fc3778d3374c3b9f36f2de06dadfcec6c8fc39a2826c7ba0"
    author = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    assert author["passed"] is True and author["checks_count"] == 90
    assert sha(HERE / "review" / "independent_replay.py") == "6ebf24406648eabd745744b9d6ca59c37e5c9c65ccff8a09dfb684ac9b7d254a"
    assert sha(HERE / "review" / "independent-verdict.json") == "ad77e8db21ed5ddcc813c034d827697a369bc92349f7de946f70ad5719187c00"
    assert sha(HERE / "review" / "independent-static-postrun-2026-10-06.md") == "76b640d123ac4884def95049eba322dde1e9c7cc88f59f8d1349abcd07d6e569"
    independent = load(HERE / "review" / "independent-verdict.json")
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks_passed"] == 5220
    assert independent["checks_total"] == 5220 and independent["failures"] == []
    lineage = []
    for role, case_id, path, expected in (
        ("accepted_parent", "D03", ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md", "8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1"),
        ("instructional_prerequisite", "A02", ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md", "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
        ("instructional_prerequisite", "B02", ROOT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md", "bceddd5983e9187bf8be19464b04ad5b2136bf665f6d4d9d676928b8c2354c61"),
    ):
        assert sha(path) == expected
        lineage.append({"role": role, "case_id": case_id, "source_path": str(path.resolve()),
                        "bytes": path.stat().st_size, "sha256": expected})
    old = source_files(OLD)
    current = source_files(HERE)
    runs = [sealed_run("parent", PARENT, PARENT_CLOSURE_SHA),
            sealed_run("child", CHILD, CHILD_CLOSURE_SHA)]
    index = {
        "schema": "simlox-d03-var01-v011-evidence-index/v1", "case_id": "D03", "variant_id": "D03.var01",
        "version": "0.1.1", "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published", "source": current, "excluded_prelaunch_source": old,
        "excluded_prelaunch": {"status": "NO_GO_roundtrip_gate_after_calc", "native_run_started": False,
                               "review_sha256": NO_GO_SHA},
        "lineage": lineage, "accepted_runs": runs, "accepted_raw_count": 24,
        "author_checks": 90, "independent_checks": 5220,
        "scope": "one seeded aircraft, three successful missions and one completed CAL24 PM by hour 36",
        "limits": "Horizon-truncated one-seed comparison. No post-horizon recurrence, PM/mission conflict, resource shortage, PM item demand, GUI visual, cross-engine, generic PM rule or Issue18 completion.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(current), "excluded_source_files": len(old),
                      "accepted_raw": 24, "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
