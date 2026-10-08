# Reproduce the bounded original result

Run from this package directory with the bundled Python. Default commands
below are read-only; they require the original accepted and new run files at
their declared paths. They do not start SIMLOX.

```powershell
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -X utf8 -B source_gate.py --mode sealed
& $python -X utf8 -B check_roundtrip.py runs/i03-var05-in-zero-delay-v100-ssh-20261008-01
& $python -X utf8 -B validate_native_cli.py runs/i03-var05-in-zero-delay-v100-ssh-20261008-01
& $python -X utf8 -B review/independent_replay.py
& $python -X utf8 -B make_source_inventory.py
& $python -X utf8 -B make_prelaunch_manifest.py
& $python -X utf8 -B make_evidence_index.py
& $python -X utf8 -B make_evidence_index.py --dry
```

The prelaunch inventory and manifest are frozen historical point-time bytes.
The postrun index builder verifies them, the independent verdict, every
required original raw file, three distinct zero-native preflight transport
originals, the catalog archive and live typed 494-entry
prefix. The live catalog may have later entries; metadata, historical prefix
and publication-ID uniqueness remain mandatory. Unpublished tmp context is
checked through exact owned inert copies, with the original tmp path checked
when present. No accepted raw or new child original may be replaced by such a
copy. The original stdout/stderr streams and receipts are pinned separately
from any decoded tool transcript; unavailable original bytes are disclosed.

For a **new derived run**, create a new package version and unique run ID.
Rebuild the source, contract, expected full event ledger and all 5,210 report
cells before native execution. Preserve the accepted parent source/raw and
required C03/C08 pins. Freeze new source and manifest bytes; obtain an actual
zero-native SSH5 preflight and independent GO_PRELAUNCH bound to its receipt;
then use the root coordinator's serial GUI/mutex/sshd guard and native dispatch.
The existing accepted parent and child run directories must not be reused or
rerun. Seal original binary streams, PID/session/integer exits, invocation and
closure, and obtain a new independent postrun verdict before publishing.
The original [REPRODUCTION.md](REPRODUCTION.md) records this run's historical
prospective prelaunch instructions, not authority to relaunch its fixed ID.
