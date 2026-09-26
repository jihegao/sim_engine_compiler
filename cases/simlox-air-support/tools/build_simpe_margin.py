"""Two positive SIMPE-margin controls after the five rejected early periods."""
from __future__ import annotations

import hashlib
import json

from build_horizon_variants import SOURCE, REPO, set_field

ENDS = {"margin_10p5": 10.5, "margin_12": 12.0}
DEST = REPO / "data/local/simlox-case-library/v1/simpe-margin-inputs"


def main() -> None:
    if DEST.exists():
        raise FileExistsError(DEST)
    DEST.mkdir(parents=True)
    model = json.loads(SOURCE.read_text(encoding="utf-8"))
    manifest = {"parent_input": str(SOURCE.resolve()),
                "parent_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "variants": []}
    for name, end in ENDS.items():
        variant = json.loads(json.dumps(model))
        for table, field in (("Control", "SIMPE"), ("Control", "RCEND"),
                             ("ResultCollection", "RCEND")):
            set_field(variant, table, field, end)
        path = DEST / f"{name}.json"
        data = (json.dumps(variant, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path.write_bytes(data)
        manifest["variants"].append({"id": name, "end_hours": end, "input_path": str(path.resolve()),
                                     "input_sha256": hashlib.sha256(data).hexdigest(),
                                     "changed_fields": ["Control.SIMPE", "Control.RCEND", "ResultCollection.RCEND"]})
    (DEST / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
