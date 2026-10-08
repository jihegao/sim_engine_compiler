# Author development history before original proof

These are local decoded tool observations only. No original stdout/stderr byte stream or typed exit receipt was captured for either failure, so this note makes no original-stream claim.

1. `classify-v1-wrong-event-count.py.bytes` (SHA-256 `a7aef690dcc24f1f07dd3879fa874630035d2c31c001dcfb67336aa07fec3f65`) was executed against the accepted read-only recovery. Its hand-entered event category counts failed before ledger evaluation. A separate read-only count of the already accepted 117-line/103-timed log showed 19 failure-clock, 10 System-ready, 7 ready-increment, and 6 ready-list lines; the active classifier uses these counts. No input, original or copy was altered.
2. `self-check-v1-continuation-uniqueness.py.bytes` (SHA-256 `d251c966d103c86b912b03a85cb7d29de1440480ca543eab88cb49175308c177`) tried to mutate a continuation pair with a helper that required the pair to occur once. It occurs four times after the four return lines, so the test harness failed before its semantic assertion. The active self-check targets one occurrence and also ties each continuation to its return or priority-list line.

The active author code later passed decoded-only local runs of source gate, sealed classification and 29 private negative clones. Those development observations are not original captured acceptance or independent signoff. Root will run frozen methods through a separate original-stream capture gate.
