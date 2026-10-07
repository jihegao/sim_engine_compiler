# Author helper draft rejected before source freeze

The second mutable helper passed local PowerShell 5 tests of exit 0, exit 7, invalid UTF-8/NUL/CRLF original byte capture, and injected session-observation failure. Root static review found a distinct failure path: a fallback drain setup exception inside `finally` could bypass `WaitForExit`, risking mutex release while a started child remains active. This was not observed in native execution; no SIMLOX was invoked. The exact pre-fix helper and test bytes are preserved here.
