# Preserved postrun index draft

The first read-only dry builder rejected this package's exact `.gitattributes`
bytes because its assertion omitted the existing final LF. The original
builder draft is preserved byte-identically beside this note. The command's
exit code was 1 and the tool showed a decoded Python AssertionError at that
assertion; original stdout/stderr byte streams were not captured for this
first attempt. A second read-only dry builder reached the source-count
assertion, which still used the count from before the first draft and this
note were preserved. Its exit code was 1 and the tool showed a decoded
AssertionError; original stdout/stderr bytes were not captured. Both failed
builder drafts are retained. No index was written and no native call occurred.
The corrected builder checks `* -text` followed by LF and derives its source
count from the closed file lists. These are development failures, not behavior
or publication acceptance results.

The later dry-passing draft still reran the frozen independent and author
semantic readers on every index rebuild. Root review requested an index that
consumes their already captured original receipts and stream bytes instead.
That reviewed draft is retained separately. It did not change original run
bytes or the accepted behavior decision.

Another dry-passing draft checked captured exit codes by value without first
requiring the JSON type `int`, which could equate Boolean false with zero.
Root content review required exact integer types for captured exits and
independent check counts. The pre-correction builder is preserved separately;
the correction adds type checks and no semantic replay.

Root then identified three original zero-native SSH preflight transport files
outside the 140 mandatory accepted/child/native originals. The dry-passing
builder from before that custody finding is also retained. The final builder
requires these three original paths and their distinct map; no copy replaces
them.
