# Context-copy development attempts

The first two `copy_context.py` drafts failed while constructing Windows paths for small historical receipts. Their source bytes and any partial copies are preserved under `preserved-development/`, `preserved-root-context/`, and `preserved-root-context-v2/`. The original terminal error streams were not saved as separate files, so no byte identity is claimed for those streams.

The current `copy_context.py` uses short numbered, hash-suffixed archive names. Its `root-context-custody.json` declares 30 mandatory owned copies, exact original paths and SHA/size pins. Reproduction uses the owned copies and checks an original only if present. The earlier partial directories are historical drafts; they are never substituted for the declared copies or for any accepted or failed-child raw run file.

The first `replay_v101.py` failure and the misleading first self-check have separately preserved source and captured output bytes. Their corrected current methods are distinct files and do not change the frozen v1.0.0 run, source, or failed decisions.
