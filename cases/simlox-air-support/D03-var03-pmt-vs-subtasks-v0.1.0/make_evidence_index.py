"""Seal D03.var03 sources and accepted parent/child local raw evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "evidence-index.json"
PARENT = ROOT / "D03-calendar-pm-v1.0.0" / "runs" / "d03-calendar-v100-ssh-20261001-02"
CHILD = HERE / "runs" / "d03-var03-pmt4-task1-v010-ssh-20261006-01"
PARENT_CLOSURE_SHA = "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8"
CHILD_CLOSURE_SHA = "b587edc3e63247b079fa3410d784cd27dd3e6ee568e32fecd2969b7812a7ec6a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    excluded = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
                "independent-publication-review-2026-10-06.md"}
    return [{"path": p.relative_to(HERE).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(HERE.rglob("*")) if p.is_file() and p.name not in excluded
            and "runs" not in p.parts and "__pycache__" not in p.parts and p.suffix != ".pyc"]


def sealed(role, run, expected):
    cp, ip = run / "closure.json", run / "invocation.json"
    assert sha(cp) == expected
    closure = load(cp)
    assert closure["run_id"] == run.name and closure["invocation_sha256"] == sha(ip)
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, item in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], path
    return {"role": role, "run_id": run.name, "local_run_dir": str(run.resolve()),
            "invocation": {"bytes": ip.stat().st_size, "sha256": sha(ip)},
            "closure": {"bytes": cp.stat().st_size, "sha256": expected}, "raw": closure["raw"]}


def main():
    fixed = {
        "contract.json": "8c020a92a4be471f43d6bb401ed0c7c80b5c54b58cd6eb6e4f5a2830d5bd52bd",
        "native-input.json": "59642b8ef5ac9e48c45110223b147cf776e0be4e0e8983a2e9507b1412074a36",
        "review/independent-contract-go-2026-10-06.md": "b6f29fe0f3fbe26cbb564a687318f6600d6977feba76da8174f4b0a0c83a60fc",
        "review/independent-prelaunch-go-2026-10-06.md": "fef1a7a4146201222211e29905227867bd31dd5ba185278443eac9af8dfe24ff",
        "review/author-native-validation-2026-10-06.json": "d8898956ff84d84913d277e60b0aefbaafe444fca5553005ceaa3d2d4f07e287",
        "review/independent_replay.py": "bc50d8e724e58a35a9b5ad10a6c10fd0b8b40efe6ec967ab862fcb2efb5b262f",
        "review/independent-verdict.json": "940471117243168efbd1fbbe6c148ee3c70df75c5da7a4666375a9bcedf001e6",
        "review/independent-static-postrun-2026-10-06.md": "d0ef7094a651d1f86cefdfd1fd5a7b2c807df5370354c81a91eff09bdee5ec0d",
    }
    for name, expected in fixed.items():
        assert sha(HERE / name) == expected, name
    author = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    assert author["passed"] is True and author["checks_count"] == 95
    independent = load(HERE / "review" / "independent-verdict.json")
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks"] == 8896
    assert independent["failures"] == [] and independent["run_id"] == CHILD.name
    lineage = []
    for role, case_id, path, expected in (
        ("accepted_parent", "D03", ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md", "8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1"),
        ("instructional_prerequisite", "A02", ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md", "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
        ("instructional_prerequisite", "B02", ROOT / "B02-serial-preparation-v1.0.2" / "evidence-2026-09-29.md", "bceddd5983e9187bf8be19464b04ad5b2136bf665f6d4d9d676928b8c2354c61"),
        ("related_precedent", "J09.var05", ROOT / "J09-var05-pmt-fallback-pair-v1.0.1" / "cli-scope-signoff-2026-10-04.md", "42d1d718462057e64208b7bd1d8d45e8d2d17fece7b22b9242b0f14f62701ac9"),
    ):
        assert sha(path) == expected
        lineage.append({"role": role, "case_id": case_id, "source_path": str(path.resolve()),
                        "bytes": path.stat().st_size, "sha256": expected})
    runs = [sealed("parent", PARENT, PARENT_CLOSURE_SHA), sealed("child", CHILD, CHILD_CLOSURE_SHA)]
    index = {
        "schema": "simlox-d03-var03-v010-evidence-index/v1", "case_id": "D03", "variant_id": "D03.var03",
        "version": "0.1.0", "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published", "source": source_files(), "lineage": lineage,
        "accepted_runs": runs, "accepted_raw_count": 24, "author_checks": 95,
        "independent_checks": 8896, "independent_verdict": "GO_BOUNDED",
        "scope": "one seeded aircraft, PMT four but referenced one-hour CAL24 PM subtask at hours 24 and 49",
        "limits": "One PMT value, one referenced subtask, one seed and 60 hours. No generic precedence law, PMTD, alternate task graphs, conflict, items, GUI visual, cross-engine or overall Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(index["source"]), "accepted_raw": 24,
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
