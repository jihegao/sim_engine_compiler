"""Read-only independent exact-source audit before the v107 case SSH preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
MANIFEST = CASE / "prelaunch-manifest.json"
RUN = CASE / "runs" / "c09-var02-v107-shortage-ssh-20261007-01"
RECEIPT = CASE / "review" / "captured-process-test-ssh0-20261007T071542425Z.json"
CUSTODY = CASE / "preserved-root-context" / "actual-ssh5-helper-test-custody.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def main() -> None:
    m = load(MANIFEST)
    r = load(RECEIPT)
    c = load(CUSTODY)
    failures: list[str] = []

    def require(ok: bool, label: str):
        if not ok:
            failures.append(label)

    require(sha(MANIFEST) == "66f21ddd52d11c96756c9e24e4b3be7e6eb113e9efa24f6efecc28e5b88ec13c",
            "manifest SHA")
    require(m["schema"] == "c09-var02-v107-prelaunch-manifest/v1", "manifest schema")
    require(m["source_count"] == len(m["source_files"]) == 1726, "manifest count")
    require(m["contract_sha256"] == sha(CASE / "contract.json"), "contract SHA")
    require(m["run_id"] == RUN.name and not RUN.exists(), "reserved child absence")
    require(m["native_runs_authorized_by_manifest"] == 0, "manifest grants no native")
    keys = set()
    for item in m["source_files"]:
        key = item["key"]
        require(key not in keys, f"duplicate key {key}")
        keys.add(key)
        path = Path(item["path"])
        require(path.is_file(), f"missing {key}")
        if path.is_file():
            require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                    f"SHA/size {key}")
    expected = {
        "runner_script": ("run_native_ssh.ps1", "328bb29a8b4286e30251c9ec397301e4cbf0ad1cb4f1d916d3a1c8e6d721600c"),
        "behavior_validator": ("validate_native_cli.py", "43192622d57766fda4efe53ef2f58215b78ba40a7bf911881962ad58b9b0b671"),
        "shortage_input": ("shortage-input.json", "a036c16bbdd28b35047ba8a064722c6a1bde21c036435263dd5713dd710767a4"),
    }
    indexed = {item["key"]: item for item in m["source_files"]}
    for key, (name, digest) in expected.items():
        require(key in indexed and indexed[key]["sha256"] == sha(CASE / name) == digest,
                f"identity {key}")
    require(not (CASE / "review" / "independent-prelaunch-go.json").exists(), "approval must be absent")

    require(sha(RECEIPT) == "284536da21a7e92e58cae94ec5e22f3820d7c65cada1d2636a6fea556804c9c9",
            "harmless SSH receipt SHA")
    require(r["status"] == "passed" and r["local_static"] is False
            and r["ssh_session"] == 0 and r["powershell_major"] == 5
            and "sshd.exe" in r["ssh_ancestors"] and r["gui_verified"] is True
            and r["mutex_free"] is True and r["run_absent"] is True
            and r["native_process_started"] is False and r["negative_rejections"] == 26,
            "harmless SSH receipt semantics")
    require([item["observed_exit"] for item in r["harmless_python"]] == [0, 7, 0, 7],
            "harmless OS exit capture")
    for name, key in (("captured_process.ps1", "helper"), ("test_captured_process.ps1", "test")):
        require(r[f"{key}_sha256_before"] == r[f"{key}_sha256_after"] == sha(CASE / name),
                f"harmless test source {key}")
    require(c["raw_file_count"] == len(c["raw"]) == 10, "helper custody count")
    require(c["receipt_identity"]["sha256"] == sha(RECEIPT), "helper custody receipt")
    listed = {item[stream]["path"]: item[stream]
              for item in r["harmless_python"] + [r["injected_post_start_failure"]]
              for stream in ("stdout", "stderr")}
    require(len(listed) == 10, "helper stdout/stderr uniqueness")
    for item in c["raw"]:
        original = Path(item["original_path"])
        owned = CASE / item["owned_copy_path"]
        require(item["original_path"] in listed, f"unlisted helper raw {original}")
        for path, label in ((original, "original"), (owned, "owned")):
            require(path.is_file(), f"missing helper {label} {path}")
            if path.is_file():
                require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                        f"helper {label} SHA/size {path}")
    output = {"decision": "PASS" if not failures else "FAIL",
              "manifest_sha256": sha(MANIFEST), "source_records": len(keys),
              "helper_raw_copies": len(c["raw"]), "reserved_child_absent": not RUN.exists(),
              "failures": failures}
    print(json.dumps(output, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
