# Read-only reproduction and future launch gates

Run the bundled Python with `-X utf8 -B`. The following commands verify
source, accepted-parent evidence and prospective expectations without starting
SIMLOX. Run them from this package directory after its canonical inventory and
manifest have been frozen:

```powershell
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -X utf8 -B build.py
& $python -X utf8 -B copy_context.py
& $python -X utf8 -B source_gate.py
& $python -X utf8 -B self_check.py
& $python -X utf8 -B test_sealed_catalog.py
& $python -X utf8 -B review/independent_replay.py --pure-fixture
& $python -X utf8 -B review/independent_self_check.py
& $python -X utf8 -B make_source_inventory.py --dry
& $python -X utf8 -B make_prelaunch_manifest.py --dry
```

The accepted I03.var01 input, full report and original raw files, all declared
C03/C08 prerequisites, eight required documents, three installed files and
80 local/Git source identities are mandatory. Unpublished tmp design records
are retained as byte-identical inert copies and checked at their original
paths only when present. The exact 494-entry historical catalog archive and
base Git blob are immutable. Sealed replay always checks the live catalog's
typed first 494 entries, metadata and unique IDs, including after authorized
later append; a future whole-file hash is an observation rather than a
substitute for that gate.

A future new execution requires a fresh package version and unique run ID,
updated source/contract/runner/independent-method review, one-time source
inventory and manifest freeze, actual SSH5 `-PreflightOnly`, independent
GO_PRELAUNCH bound to its exact receipt, then the root coordinator's sole
native dispatch under a fresh GUI/mutex/sshd/source guard. The existing run
directory must remain absent until that dispatch. Never rerun the accepted
parent or reuse its run path. The original binary stage streams, child
PID/session/integer exit, source maps, six ordered stages, invocation and
closure must be sealed before any bounded publication decision.

The prospective validators intentionally fail closed if the child differs
from the predeclared h10 task/receipt sequence or any expected report cell.
See the accepted parent package for its historical SSH execution evidence;
these instructions do not authorize repeating it.
