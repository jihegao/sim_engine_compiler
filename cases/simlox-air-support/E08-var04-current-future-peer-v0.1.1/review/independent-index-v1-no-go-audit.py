"""Read-only audit of the preserved first E08.var04 publication index hazard."""

import hashlib
import json
import pathlib
import subprocess


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
INDEX = PACKAGE / "evidence-index.json"
INDEX_SHA = "d54410100e50d0ed0b1ca866fea79a4e2b9b91f0510a3542d32e7b305b095bb3"
BUILDER_SHA = "950299db9455db144d09ae4f2b9d8bf43ec96dccb6b87ebf2f677faf3c65c5e6"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert sha(INDEX.read_bytes()) == INDEX_SHA
    assert sha((PACKAGE / "make_evidence_index.py").read_bytes()) == BUILDER_SHA
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert len(index["source_files"]) == 118
    for record in index["source_files"]:
        data = (PACKAGE / record["path"]).read_bytes()
        assert len(data) == record["bytes"] and sha(data) == record["sha256"], record["path"]
    archived = [record for record in index["source_files"] if record["path"].startswith("preserved-excluded-source/")]
    assert len(archived) == 22
    for version in ("v1.0.0", "v1.0.1"):
        directory = PACKAGE / "preserved-excluded-source" / f"E08-var01-immediate-lateral-{version}"
        assert (directory / ".gitattributes").read_bytes().startswith(b"* text eol=lf")
        candidate = directory / "build.py"
        path = candidate.relative_to(ROOT).as_posix()
        output = subprocess.check_output(["git", "check-attr", "text", "eol", "--", path], cwd=ROOT, text=True)
        assert ": text: set" in output and ": eol: lf" in output, output
    return {"decision": "NO_GO_PUBLICATION_ARCHIVE_ATTRIBUTES", "index_sha256": INDEX_SHA,
            "old_source_disk_pins": 118, "old_excluded_archive_files": 22,
            "reason": "nested .gitattributes activates text/eol=lf for archived children, overriding the enclosing inert-byte policy; no staged blob mismatch is asserted"}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
