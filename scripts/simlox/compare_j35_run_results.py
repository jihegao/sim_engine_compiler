"""Report exact Python/Rust RunResult differences without smoothing them away."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(left: object, right: object, path: str = "$", out: list | None = None) -> list:
    if out is None:
        out = []
    if type(left) is not type(right):
        out.append({"path": path, "left": left, "right": right, "kind": "type"})
    elif isinstance(left, dict):
        for key in sorted(left.keys() | right.keys()):
            if key not in left or key not in right:
                out.append({"path": f"{path}.{key}", "left": left.get(key), "right": right.get(key), "kind": "missing"})
            else:
                differences(left[key], right[key], f"{path}.{key}", out)
    elif isinstance(left, list):
        if len(left) != len(right):
            out.append({"path": path + ".length", "left": len(left), "right": len(right), "kind": "length"})
        for i, (a, b) in enumerate(zip(left, right)):
            differences(a, b, f"{path}[{i}]", out)
    elif left != right:
        row = {"path": path, "left": left, "right": right, "kind": "value"}
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            row["absolute_difference"] = abs(left - right)
        out.append(row)
    return out


def compare(left_path: Path, right_path: Path) -> dict:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    diff = differences(left, right)
    return {
        "left": {"path": str(left_path), "sha256": sha256(left_path)},
        "right": {"path": str(right_path), "sha256": sha256(right_path)},
        "top_level_fields_exact": {
            key: left.get(key) == right.get(key) for key in sorted(left.keys() | right.keys())
        },
        "exact_difference_count": len(diff),
        "exact_differences": diff,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = compare(args.left, args.right)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exact_difference_count": report["exact_difference_count"], "top_level_fields_exact": report["top_level_fields_exact"]}))


if __name__ == "__main__":
    main()
