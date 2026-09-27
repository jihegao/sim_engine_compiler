#!/usr/bin/env bash
# Package this completed window only; never execute a simulation.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
run=runs/cpu-batch-v1/run-20260927T055817Z-2557785
prep=runs/cpu-batch-v1-preparation
out=benchmarks/cpu_batch_v1/results/amd128-20260927
test "$(sha256sum "$run/manifest.json" | cut -d ' ' -f1)" = b529e41107a9b547c9329a10902da2559aed661c699c4027f9d95e077a0231d3
test "$(jq -r .status "$run/measurement/state.json")" = completed
test "$(jq -r .cells_completed "$run/measurement/state.json")" = 56

# Eight host/process snapshots remain local. Preserve the original state hash;
# the separately named derivative must never stand in for the sealed original.
jq --arg original_sha256 "$(sha256sum "$run/measurement/state.json" | cut -d ' ' -f1)" \
  'del(.machine_before,.machine_after) + {publication_derivative: {
    original_local_sha256: $original_sha256,
    omitted_fields: ["machine_before", "machine_after"],
    reason: "Unrelated host process arguments retained locally, not published"
  }}' "$run/measurement/state.json" | tee "$out/state-public.json" >/dev/null

public_files() {
  find "$run" "$prep" -type f \
    ! -path "$run/machine-freeze.json" \
    ! -path "$run/measurement/state.json" \
    ! -path "$run/preflight-processes.log" \
    ! -path "$run/preflight-final-processes.log" \
    ! -path "$run/preflight-top.log" \
    ! -path "$run/preflight-final-top.log" \
    ! -path "$run/window-known-tools.log" \
    ! -path "$run/window-top.log" -print0 | sort -z
}
public_files | xargs -0 sha256sum | tee "$out/raw-files.sha256" >/dev/null
tar --sort=name --mtime='2026-09-27 00:00:00Z' --owner=0 --group=0 \
  --numeric-owner -czf "$out/raw-evidence.tar.gz" \
  --null -T <(public_files)
for name in manifest.json summary.json; do
  if test -e "$out/$name"; then
    cmp "$run/$name" "$out/$name"
  else
    cp "$run/$name" "$out/$name"
  fi
done
(
  cd "$out"
  sha256sum raw-evidence.tar.gz raw-files.sha256 manifest.json summary.json \
    state-public.json | tee SHA256SUMS
)
