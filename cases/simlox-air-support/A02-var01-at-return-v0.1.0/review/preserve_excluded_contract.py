"""Reconstruct and retain the independently rejected A01-provenance draft."""
from pathlib import Path
import hashlib

here = Path(__file__).resolve().parent
current = (here.parent / "contract.json").read_bytes()
prefix, remainder = current.split(b'  "prerequisite_a01": {', 1)
section, suffix = remainder.split(b'  "source": {', 1)
added = (
    b'contract_sha256', b'signoff_sha256', b'evidence_index_sha256',
    b'final_run_id', b'final_closure_sha256', b'replay_run_id',
    b'replay_closure_sha256',
)
section = b"".join(
    line for line in section.splitlines(keepends=True)
    if not any(line.lstrip().startswith(b'"' + key + b'"') for key in added)
)
old = prefix + b'  "prerequisite_a01": {' + section + b'  "source": {' + suffix
expected = "d3bc8a369eaeaa0a4823c563e5c256840c7142284a1815d9c0ea156a069e4faf"
actual = hashlib.sha256(old).hexdigest()
if actual != expected:
    raise ValueError(f"reconstructed NO_GO draft hash differs: {actual}")
output = here / "excluded-contract-a01-provenance.json"
if output.exists() and output.read_bytes() != old:
    raise ValueError("preserved NO_GO draft differs")
output.write_bytes(old)
print(actual)
