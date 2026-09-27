# Evidence package and verification boundary

This directory records the one completed CPU batch window on 2026-09-27.
It is not permission to repeat the window. The frozen protocol and pre-freeze
review retain their historical preparation status; the result is a new receipt.

- `REPORT.md`: human-readable findings and measurement limitations.
- `manifest.json`, `summary.json`: byte-for-byte copies of the frozen identity
  and validated summary, not regenerated or path-rewritten versions.
- `raw-evidence.tar.gz`: publishable original run and preparation files, with
  their relative `runs/` paths preserved; eight private host snapshots excluded.
- `raw-files.sha256`: SHA-256 inventory of every file in the archive.
- `SHA256SUMS`: hashes for the archive, inventory and readable copied JSON.
- `independent-data-review.json`: separate post-window data review; not a
  replacement for the pre-freeze harness review.
- `publication-review.json`: safety review and exact excluded-file hashes.
- `state-public.json`: explicitly named derivative of the completed state,
  omitting machine snapshots and binding the unchanged local original's hash.
- `package-evidence.sh`: exact offline packaging commands, no model execution.

The archive includes all 56 cell reports, commands, stdout/stderr and GNU-time
outputs; semantic admission raw trees; the actual-eight-worker supplement;
immutable seed/schedule files; compiled Plan and
Business/Core/lineage; and preparation/measurement commands. No native binary,
virtual environment, database, credential file or upstream live service is
included. Executable bytes are identified by hashes in the manifest.

The unchanged local-only files are `machine-freeze.json`,
`measurement/state.json`, `preflight-processes.log`,
`preflight-final-processes.log`, `preflight-top.log`,
`preflight-final-top.log`, `window-known-tools.log`, and `window-top.log`.
Their complete process inventories include unrelated personal information and
are deliberately not published. The frozen manifest still identifies the
original local machine snapshot: it does not claim that snapshot is in the tar.
Independent data review inspected these local originals. Public readers can
verify their recorded hashes only if separately authorized to access them;
the public package alone cannot reproduce the full monitoring audit.

To inspect offline in a new empty directory, first check `SHA256SUMS`, extract
the archive, then run `sha256sum -c /absolute/path/to/raw-files.sha256` from the
extraction root. Inventory paths are relative to that root. Do not extract over
an existing run directory. These checks need no model execution or installed
compiler. The archive retains original absolute paths inside JSON and commands
as provenance; it is not a relocatable executable environment.

The live-checkout `driver.py summarize` additionally checks current installed
artifacts, source, Plan and all raw report seals against the frozen manifest.
It succeeded after this sole window. It is intentionally stricter than offline
archive inspection and is not expected to accept a different installation by
rewriting frozen paths or identities. Reproduction requires a separately
authorized fresh experiment, not resumption of this evidence directory.

The hashes provide consistency, not third-party authentication. The independent
review ran on the same host and is not an external replication. Complete raw
results establish the named semantic gates; performance cells retain backend
proofs, not a second complete result-tree export from every Rust timing call.
Monitoring supports controlled best-effort/no observed known-heavy overlap,
not OS idleness. The initial known-tool scan cadence deviation is disclosed in
the report; original monitoring files are retained unchanged locally.

CI runs synthetic harness controls and the existing semantic suite, never this
performance window. Exact final-head CI is reported in the separate Draft PR
after it finishes, to avoid a self-referential commit/hash receipt. This package
does not merge a PR, close Issue #6, or authorize an optimization.
