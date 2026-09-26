"""A01 result-window probes: preserve SIMPE=36 and vary only RCEND fields."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_horizon_variants import ENDS, SOURCE, REPO, set_field

DEST = REPO / "data/local/simlox-case-library/v1/collection-inputs"


def main() -> None:
    if DEST.exists():
        raise FileExistsError(DEST)
    DEST.mkdir(parents=True)
    model = json.loads(SOURCE.read_text(encoding="utf-8"))
    manifest = {"parent_input": str(SOURCE.resolve()),
                "parent_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "purpose": "SIMPE stays 36 h; only the result collection window changes",
                "variants": []}
    for name, end in ENDS.items():
        variant = json.loads(json.dumps(model))
        set_field(variant, "Control", "RCEND", end)
        set_field(variant, "ResultCollection", "RCEND", end)
        path = DEST / f"{name}.json"
        data = (json.dumps(variant, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path.write_bytes(data)
        manifest["variants"].append({"id": name, "end_hours": end,
                                     "input_path": str(path.resolve()),
                                     "input_sha256": hashlib.sha256(data).hexdigest(),
                                     "changed_fields": ["Control.RCEND", "ResultCollection.RCEND"]})
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
