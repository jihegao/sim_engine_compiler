"""Derive a BASE-01 OUT transfer from accepted E08's enabled lateral arm."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2" / "on-input.json"
PARENT_SHA = "630d7600e7ff77ddb057f05af0852b4f41ed6335718570f9fcf5eddd9f51c474"
TRANSFER_SOURCE = HERE.parent / "I02-var02-out-transfer-v1.0.0" / "native-input.json"
TRANSFER_SOURCE_SHA = "7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc, name):
    match = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(match) != 1:
        raise ValueError(name)
    return match[0]


def build():
    if sha(PARENT) != PARENT_SHA or sha(TRANSFER_SOURCE) != TRANSFER_SOURCE_SHA:
        raise ValueError("published parent or transfer schema source changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "I02.var08 BASE-01 OUT1 at h2 with stocked peer BASE-02 and ENLAT=Y"
    )
    template = copy.deepcopy(table(json.loads(TRANSFER_SOURCE.read_text(encoding="utf-8")), "ItemTransfer"))
    assert [c["name"] for c in template["columns"]] == ["STFID", "STTID", "IID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    template["instances"][0]["rows"] = [["BASE-01", "<OUTSIDE>", "TEACH-LRU-01", 2.0, 1, 0.0, None]]
    doc["model"]["tables"].append(template)
    return doc


if __name__ == "__main__":
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "native-input.json"
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("frozen source differs")
    else:
        output.write_bytes(raw)
    print(json.dumps({"source_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
