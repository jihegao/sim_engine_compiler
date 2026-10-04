# I06 v1.0.1 scheduled reliability panel

This accepted bounded panel pairs three fixed seeds for each of two changes: traditional primary-item `ChangesItemReliability.FRTCF` under OPHOURS, and position-linked `ChangesFailureModeReliability.FRQCF` under CALHOURS. Each control sets factor 1 at h9 and h24. Each intervention sets factor 4 at h9 and returns to factor 1 at h24. The [frozen contract](contract.json) defines the inputs and publication gates; the [signoff](cli-scope-signoff-2026-10-05.md) states the observed result and limits.

The guarded session-0 [native run](run_native_ssh.ps1) completed 48 steps and sealed 122 raw files. [Author validation](review/author-validation-2026-10-05.json) passed 306/306 checks and [independent replay](review/independent-verdict.json) passed 2704/2704 with a bounded GO. The [evidence index](evidence-index.json) records the source and local raw hashes. Raw runs remain local and ignored by Git.

The frozen [v1.0.0 diagnostic](../I06-var01-02-scheduled-reliability-v1.0.0/README.md) failed its h24 exposure gate and has no publication-index entry. v1.0.1 moves the traditional item's third mission to h23–25 for every arm; the failure-mode inputs remain byte-identical to v1.0.0.
