"""Read-only proof of the conditional catalog check-count drift after append."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PKG = Path(__file__).resolve().parent.parent
REPO = PKG.parents[2]
INDEX_SHA = "57d5ebba2f372f7f07ef092e5c2de58a5577988ade19587f13e522e3706339d8"
METHOD_SHA = "e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e"
VERDICT_SHA = "67265c50b84e1ea1c325914e5ecd4988e58a2548e1fbe02b4ca2340d143a13c6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert sha(PKG / "evidence-index.json") == INDEX_SHA
    assert sha(PKG / "review/independent_replay_v3.py") == METHOD_SHA
    old_path = PKG / "review/independent-postrun-verdict-v3.json"
    assert sha(old_path) == VERDICT_SHA
    old = json.loads(old_path.read_text(encoding="utf-8"))
    run = subprocess.run([sys.executable, "-X", "utf8", "-B",
                          str(PKG / "review/independent_replay_v3.py")],
                         cwd=REPO, capture_output=True, check=True)
    assert run.stderr == b""
    current = json.loads(run.stdout.decode("utf-8-sig"))
    assert old["checks"] == 14996 and current["checks"] == 14995
    old_without_count = {k: v for k, v in old.items() if k != "checks"}
    now_without_count = {k: v for k, v in current.items() if k != "checks"}
    assert now_without_count == old_without_count
    index = json.loads((PKG / "evidence-index.json").read_text(encoding="utf-8"))
    catalog = index["catalog_history"]
    archive = json.loads((PKG / catalog["owned_archive"]).read_text(encoding="utf-8"))
    live = json.loads((REPO / catalog["path"]).read_text(encoding="utf-8"))
    assert len(archive["entries"]) == 490 and len(live["entries"]) == 491
    assert live["entries"][:490] == archive["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in archive.items() if k != "entries"}
    method = (PKG / "review/independent_replay_v3.py").read_text(encoding="utf-8")
    assert 'if len(live["entries"]) == 490:' in method
    assert '"catalog prepublication exact"' in method
    builder = subprocess.run([sys.executable, "-X", "utf8", "-B",
                              str(PKG / "make_evidence_index.py")],
                             cwd=REPO, capture_output=True)
    assert builder.returncode != 0 and b"AssertionError" in builder.stderr
    print(json.dumps({"schema": "i03-var02-independent-publication-v1-no-go/v1",
                      "decision": "NO_GO_PUBLICATION_REPRO_V1",
                      "index_sha256": INDEX_SHA,
                      "old_checks": old["checks"], "postappend_checks": current["checks"],
                      "same_other_verdict_fields": True,
                      "catalog_old_entries": 490, "catalog_live_entries": 491,
                      "v1_dry_builder_failed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
