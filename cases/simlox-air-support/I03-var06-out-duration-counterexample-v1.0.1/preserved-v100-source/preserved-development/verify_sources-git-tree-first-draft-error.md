# Author development failure: Git tree traversal

The first mutable `verify_sources.py` run failed before source verification at `git_tree` line 49, with `AssertionError` while requiring every entry in `git ls-tree -r -z` to be a regular executable/nonexecutible blob. The repository tree may also contain other entry modes. The correction skips entries outside the exact source-pin lookup and still requires every pinned source path to resolve to a blob. This is an author code-development failure, not a native SIMLOX outcome.

The full first-draft source bytes are preserved beside this note. The interactive tool traceback is available in the task transcript; no exact stdout/stderr byte files were saved for this draft.
