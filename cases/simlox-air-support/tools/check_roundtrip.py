"""Gate native calc on exact nonempty business-row jimport/jexport roundtrip."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from validate_native import compare_roundtrip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("export", type=Path)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    result = compare_roundtrip(args.input, args.export)
    if args.result.exists():
        raise FileExistsError(args.result)
    args.result.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"all_equal": result["all_equal"], "nonempty_business_tables": result["nonempty_business_tables"]}))
    if not result["all_equal"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
