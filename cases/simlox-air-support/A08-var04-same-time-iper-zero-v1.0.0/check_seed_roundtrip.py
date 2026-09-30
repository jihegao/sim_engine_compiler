"""Verify one generated seed input survived the native import/export roundtrip."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from check_roundtrip import parse_native, populated


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    run = Path(sys.argv[1])
    expected = sys.argv[2]
    issues: list[str] = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if not issues:
        if sha(run / "input.json") != expected:
            issues.append("input SHA differs")
        source = populated(parse_native(run / "input.json"))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        if len(source) != 13:
            issues.append(f"expected 13 populated source tables, found {len(source)}")
        for name, table in source.items():
            if exported.get(name) != table:
                issues.append(f"source rows/columns differ in {name}")
        if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
            issues.append("import completion marker absent")
        if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
            issues.append("export completion marker absent")
    result = {"schema": "simlox-a08-var04-seed-roundtrip/v1", "passed": not issues,
              "differences": issues, "input_sha256": expected,
              "roundtrip_sha256": sha(run / "roundtrip-raw.json") if not issues else None,
              "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
