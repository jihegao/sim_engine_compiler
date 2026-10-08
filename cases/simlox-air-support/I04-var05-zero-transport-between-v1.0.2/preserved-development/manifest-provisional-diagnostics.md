# Provisional manifest draft failures

Two local read-only provisional invocations exited 1 while adapting the copied v1.0.0 manifest builder. The first still referenced an absent owned parent-prelaunch-manifest.json.bytes; the second still expected the old 52-row context map. Their respective exact source drafts are preserved beside this note as make-manifest-v100-path-assumption.py.bytes and make-manifest-v100-context-assumption.py.bytes.

The command tool returned decoded traceback text and integer exits. No original binary stdout/stderr capture or receipt was created for those two draft calls. The corrected builder uses the frozen v1.0.0 prelaunch manifest and the v1.0.1 131-row context map. Neither failure invoked SSH or SIMLOX.
