"""Seal J06.var02 tracked source and immutable local System replication output."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/j06-system-replication-v101-ssh-20261004-01"
INDEX = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and
                   "runs" not in p.relative_to(HERE).parts and
                   "__pycache__" not in p.relative_to(HERE).parts and
                   p.name not in {"evidence-index.json", "cli-scope-signoff-2026-10-04.md"})
    source = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files]
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or closure["invocation_sha256"] != sha(RUN / "invocation.json"):
        raise ValueError("run did not close cleanly")
    for name, seal in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    parent = ROOT / "J04-var01-fixed-replications-v1.0.0"
    diagnostic = ROOT / "J06-system-replication-percentile-v1.0.0"
    return {"schema": "simlox-j06-var02-system-replication-evidence-index/v1", "case_id": "J06", "variant_id": "J06.var02",
            "version": "1.0.1", "publication_state": "not_published", "source": source,
            "accepted_parent": {"package": parent.name, "input_sha256": sha(parent / "probe-input.json"),
                                "closure_sha256": sha(parent / "runs/j04-var01-fixed-reps-accepted-20261001-03/closure.json")},
            "excluded_diagnostic": {"package": diagnostic.name,
                                     "closure_sha256": sha(diagnostic / "runs/j06-system-replication-v100-ssh-20261004-01/closure.json")},
            "run": {"state": "accepted_candidate", "run_id": RUN.name, "local_path": str(RUN),
                    "closure_sha256": sha(RUN / "closure.json"), "invocation_sha256": closure["invocation_sha256"], "raw": closure["raw"]},
            "report_settings": {"local_path": str(HERE / "runs/report-settings/replications-enabled.sxs"),
                                "sha256": sha(HERE / "runs/report-settings/replications-enabled.sxs"),
                                "installed_default_sha256": sha(Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")),
                                "changed_byte_offset": 67165},
            "raw_location_policy": "local_only_ignored_runs_not_committed"}


if __name__ == "__main__":
    raw = (json.dumps(build(), indent=2) + "\n").encode()
    INDEX.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
