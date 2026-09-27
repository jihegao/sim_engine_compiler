# C03 static CI follow-up

Task: `simlox-c03-static-ci-af2fffc-v1`. The original preparation is commit
`af2fffc7e644b588f104918337c7b4112462801d`; its manifest, 15 artifacts, five
dependencies, 12 conformance tests and historical review records stay unchanged.

PR26 targets `codex/simlox-case-library-a01-a02` at
`861ce9e193046bc1c8cec276fdb85101044dbfaa`. The inherited integration workflow
only listens for PRs targeting main and supplied **no** check for af2fffc.
Historical PR21 checks and the prior local static results are not this new
head's CI acceptance.

The dedicated `simlox-c03-static.yml` workflow accepts the actual stacked base
and main, with path filters for the C03 package and its source dependencies. It
checks out the exact pull-request head, not an unidentified merge tree. It uses
Python 3.12 and stdlib only, read-only contents permission, no persisted checkout
credentials, and a five-minute timeout. It starts no engine or native process.

`scripts/check_simlox_c03_static.py` performs the actual preparation command and
discovers/executes the existing C03 unittest module. Its receipt records head,
base, base branch, checkout tree, workflow/checker hashes, manifest and contract
hashes, six input hashes, discovered/started test identities, actual passed and
skipped counts, raw log hashes and action-run identity. Acceptance requires
exactly 12 discovered, started, executed and passed, with zero skips, failures,
errors, expected failures or unexpected successes. Missing tests cannot pass.
The pinned original manifest must match before its contents are trusted.

The receipt and raw logs are uploaded as `c03-static-<PR-head>-<run-attempt>` even
when the check fails. Current CI success must be read from the exact new head's
GitHub run and downloaded receipt; this document is not a pre-issued CI pass.

Local reproduction from a clean checkout (output must be new):

```sh
python3 scripts/check_simlox_c03_static.py \
  --head "$(git rev-parse HEAD)" \
  --base 861ce9e193046bc1c8cec276fdb85101044dbfaa \
  --base-ref codex/simlox-case-library-a01-a02 \
  --output /tmp/c03-static-new
```

This closes only the static CI gap. Keep GUI/model review and native parent
acceptance B01 -> B02 -> C01 -> C02 as visible prerequisites for future C03
execution. Shared-pool scope, scarce joint acquisition, native identities and
phase order remain unverified. No SIMLOX/GUI/runner/scheduler/replay/performance
execution, engine-line delegation, PR retargeting or merge is authorized here.
