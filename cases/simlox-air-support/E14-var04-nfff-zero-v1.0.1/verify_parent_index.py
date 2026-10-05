"""Verify the accepted E14 index's distinct local and published byte identities."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo, object_spec, local_path, local_sha, local_size, git_sha, git_size = sys.argv[1:]
    local = Path(local_path).read_bytes()
    published = subprocess.check_output(["git", "-C", repo, "show", object_spec])
    assert len(local) == int(local_size)
    assert hashlib.sha256(local).hexdigest() == local_sha
    assert len(published) == int(git_size)
    assert hashlib.sha256(published).hexdigest() == git_sha
    assert local.replace(b"\r\n", b"\n") == published
    assert json.loads(local) == json.loads(published)
    print(json.dumps({"local_sha256": local_sha, "published_git_sha256": git_sha}))


if __name__ == "__main__":
    main()
