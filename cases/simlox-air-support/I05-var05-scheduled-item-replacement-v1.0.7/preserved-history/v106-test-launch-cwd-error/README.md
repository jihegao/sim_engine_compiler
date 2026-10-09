# v1.0.6 local test launch error

At 2026-10-09 12:18 UTC, the unittest command was invoked from the repository root instead of the case directory. Python could not import `test_roundtrip_policy`; zero test methods ran. This was a command working-directory error, not a checker result or native attempt. The same 14 tests were then run from the case directory and passed.
