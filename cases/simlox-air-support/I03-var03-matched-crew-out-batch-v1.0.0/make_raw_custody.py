"""Pin mandatory original parent, prerequisite and paired-run bytes; no copying."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from source_gate import HERE, REPO, RUN_IDS, unique_json, verify
from copy_postrun_context_v2 import verify as verify_context

OUT = HERE / "raw-custody-map.json"
ROOT_SEALS = {
    "control_out1": REPO / "tmp/i03-var03-root-seal-ssh-native-control_out1-20261007T233143347757Z-341e8041.json",
    "child_out2": REPO / "tmp/i03-var03-root-seal-ssh-native-child_out2-20261007T233848248287Z-c67f6a7a.json",
}


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    verify("sealed", "control_out1")
    verify_context()
    context = unique_json((HERE / "postrun-context-custody-v2.json").read_bytes())
    context_by_original = {row["original"]: row for row in context["records"]}
    contract = unique_json((HERE / "contract.json").read_bytes())
    rows: list[dict] = []
    for row in contract["source_lineage"]["accepted_parent_original_raw"]:
        path = Path(row["path"])
        wanted = {k: row[k] for k in ("bytes", "sha256")}
        assert pin(path) == wanted
        rows.append({"role": "accepted_parent_original", "path": str(path), **wanted})
    assert len(rows) == 34
    prereq = unique_json((HERE / "preserved-root-context/i03-var03-root-prerequisite-seals-v2-20261008.json.bytes").read_bytes())
    for row in prereq["records"]:
        if row["role"] == "mandatory_original_raw":
            path = Path(row["path"])
            wanted = {k: row["observed"][k] for k in ("bytes", "sha256")}
            assert pin(path) == wanted
            rows.append({"role": "accepted_prerequisite_original", "path": str(path), **wanted})
    assert len(rows) == 112
    for arm, run_id in RUN_IDS.items():
        relative_seal = ROOT_SEALS[arm].relative_to(REPO).as_posix()
        assert relative_seal in context_by_original
        context_row = context_by_original[relative_seal]
        owned_seal = HERE / context_row["owned_copy"]
        assert pin(owned_seal) == {k: context_row[k] for k in ("bytes", "sha256")}
        seal = unique_json(owned_seal.read_bytes())
        assert seal["arm"] == arm and seal["run_id"] == run_id
        directory = HERE / "runs" / run_id
        files = seal["owned_files"]
        assert len(files) == 25 and {p.name for p in directory.iterdir() if p.is_file()} == set(files)
        for name in sorted(files):
            path = directory / name
            wanted = {k: files[name][k] for k in ("bytes", "sha256")}
            assert pin(path) == wanted
            rows.append({"role": "new_" + arm + "_original", "path": str(path), **wanted})
    assert len(rows) == 162 and len({row["path"] for row in rows}) == 162
    return {"schema": "i03-var03-mandatory-original-raw-custody/v1", "records": rows,
            "accepted_prior": 112, "control_original": 25, "child_original": 25,
            "location_rule": "original paths mandatory; owned small-proof copies never substitute for these raw bytes"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = candidate()
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.write:
        assert not OUT.exists(), "preserve existing raw custody map"
        OUT.write_bytes(data)
    elif OUT.exists():
        assert OUT.read_bytes() == data, "raw custody map differs from original bytes"
    print(json.dumps({"schema": value["schema"], "records": len(value["records"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
