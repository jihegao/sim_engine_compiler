"""Execute only the pinned one-literal correction against sealed v0.2.0 raw files."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "D04-var01-over-threshold-reanalysis-v0.2.1"
SEALED = ROOT / "D04-var01-over-threshold-v0.2.0"
ORIGINAL = PRIOR / "validate_readonly.py"
CORRECTED = HERE / "validate_readonly.py"
OUTPUT = HERE / "review" / "author-readonly-validation-2026-10-06.json"
OLD_LITERAL = b"98d30d678431fb8ce6661b2cac2b5a3681b226bca32a8076c7eac8899e18dea"
FULL_LITERAL = OLD_LITERAL + b"0"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    expected = {
        HERE / "contract.json": "13677a298f2a45c1c3e2e01bb4d2451f1f9a78f3d2b789742ed2545ec3d24bbe",
        HERE / "review" / "independent-contract-go-2026-10-06.md": "2af31554f21501fb834f472ebdb1fbffe066a56d8a7565945d43c812db66d5d5",
        SEALED / "contract.json": "ea9cb13d9b40d701502b05079fafb0a36dd3f27c0bb347e12cb17d2dc8f21499",
        SEALED / "native-input.json": "35866de7c9414c9dc39e75416c3464ec00b1d6c5d2f987749c428323dc57e092",
        SEALED / "runs" / "d04-var01-op2-v020-ssh-20261006-01" / "closure.json": "7b25240fd45645f599e00ebaf6b750ac0246bba0bea1e44f1c0da0532f0e9146",
        SEALED / "validate_native_cli.py": "dd40c5a0c483475a0627cb1ad4711d7f8db55ab918565a9138502dd045e13318",
        SEALED / "review" / "failed-author-serialization-2026-10-06.txt": "61aef56b20679d9aeb618c17ff0a13a84a988c8f09877307ea43e1d25c7b7f93",
        PRIOR / "contract.json": "0d1b6b38d631413811b76596104afb2f67e15f77ceeb392ed5c8ece8317af355",
        PRIOR / "review" / "author-readonly-validation-2026-10-06.json": "a97cb3916cfc4f134fac293549003f6af145cbc21ee78d36a7252c6dd99ea619",
        ORIGINAL: "5fdc73ea6f9b328a5f6e1d4cf6283d552671e3203ddf8ee3675bec3af1ee34a7",
        CORRECTED: "2fe9b87ab96d47baf7ae6b6e5ef2ffccb9ef63d4b973ecc5b6c2a841c7623bb0",
    }
    for path, pin in expected.items():
        if sha(path) != pin:
            raise ValueError(f"frozen SHA differs: {path}")
    original, corrected = ORIGINAL.read_bytes(), CORRECTED.read_bytes()
    if original.count(OLD_LITERAL) != 1 or corrected != original.replace(OLD_LITERAL, FULL_LITERAL):
        raise ValueError("corrected checker differs beyond final sibling SHA digit")
    prior = json.loads((PRIOR / "review" / "author-readonly-validation-2026-10-06.json").read_bytes())
    failures = [x["name"] for x in prior["checks"] if not x["passed"]]
    if prior["passed"] or prior["checks_count"] != 7068 or failures != ["sibling closure SHA"]:
        raise ValueError("preserved v0.2.1 one-failure verdict differs")
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(exist_ok=True)
    # The source bytes are exact and pinned. Bind __file__ to the preserved v0.2.1
    # location so its original contract, memo and raw lineage checks run unchanged.
    namespace = {"__name__": "d04_v022_pinned_readonly_checker", "__file__": str(ORIGINAL)}
    exec(compile(corrected, str(ORIGINAL), "exec"), namespace)
    argv = sys.argv
    try:
        sys.argv = [str(ORIGINAL), "--output", str(OUTPUT)]
        code = namespace["main"]()
    finally:
        sys.argv = argv
    result = json.loads(OUTPUT.read_bytes())
    if code != 0 or not result["passed"] or result["checks_count"] != 7068 or any(not x["passed"] for x in result["checks"]):
        raise ValueError("corrected checker did not pass all original gates")
    print(json.dumps({"passed": True, "checks_count": result["checks_count"],
                      "report_sha256": sha(OUTPUT), "new_native_run": False}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
