"""Read-only direct pin audit for the frozen retrospective contract."""
import hashlib
import json
import subprocess
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
REPO = CASE.parents[2]
DATA = json.loads((CASE / "contract.json").read_bytes().decode("utf-8-sig"))
checked = []
issues = []


def h(data):
    return hashlib.sha256(data).hexdigest()


def resolve(name):
    p = Path(name)
    for candidate in (p, CASE / p, REPO / p):
        if candidate.exists():
            return candidate.resolve()
    return None


def disk(ref, path, label):
    if not path or not path.is_file():
        issues.append((label, "missing", str(path)))
        return
    data = path.read_bytes()
    if len(data) != ref["bytes"] or h(data) != ref["sha256"]:
        issues.append((label, "byte mismatch", str(path)))
    else:
        checked.append((label, str(path)))


def gitblob(ref, path, label):
    if not path:
        issues.append((label, "no local path for git", ""))
        return
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        issues.append((label, "not in repository", str(path)))
        return
    result = subprocess.run(["git", "show", f"origin/simlox/main:{rel}"], cwd=REPO,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode or len(result.stdout) != ref["bytes"] or h(result.stdout) != ref["sha256"]:
        issues.append((label, "git blob mismatch", rel))
    else:
        checked.append((label, f"origin/simlox/main:{rel}"))


def walk(value, label="root", directory=None):
    if isinstance(value, list):
        for i, part in enumerate(value):
            walk(part, f"{label}[{i}]", directory)
        return
    if not isinstance(value, dict):
        return
    here = resolve(value["path"]) if isinstance(value.get("path"), str) else directory
    if "path" in value and all(k in value for k in ("bytes", "sha256")):
        disk(value, here, label)
    if "local_disk" in value:
        disk(value["local_disk"], here, label + ".local_disk")
    if "published_git" in value:
        gitblob(value["published_git"], here, label + ".published_git")
    if here and here.is_dir():
        for field, filename in (("closure", "closure.json"), ("invocation", "invocation.json"),
                                ("model_log", "model.log"), ("report", "report-raw.json"),
                                ("failure_seal", "failure-seal.json")):
            ref = value.get(field)
            if isinstance(ref, dict) and all(k in ref for k in ("bytes", "sha256")):
                disk(ref, here / filename, label + "." + field)
        if isinstance(value.get("raw"), dict):
            for filename, ref in value["raw"].items():
                if isinstance(ref, dict) and all(k in ref for k in ("bytes", "sha256")):
                    disk(ref, here / filename, label + ".raw." + filename)
    for key, part in value.items():
        walk(part, f"{label}.{key}", here)


walk(DATA)
print(json.dumps({"contract_sha256": h((CASE / "contract.json").read_bytes()),
                  "checked_references": len(checked), "issues": issues[:30],
                  "issue_count": len(issues)}, indent=2))
if issues:
    raise SystemExit(1)
