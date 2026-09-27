# Frozen A01/A02 dependency snapshot

`a01-a02-handoff-519b209.zip` is a generated snapshot of self-authored teaching
inputs/contracts and compact native evidence references. It contains no SIMLOX
executable, SXI/SXO, raw ENLOG, database or proprietary model source.

Source was fetched from the actual GitHub remote at exact PR #21 commit
`519b2094c3be355399bc101cdcfe30d456cbb47b`, independently of this main-based
consumer branch. Neither PR #21 nor PR #20 is merged or a runtime dependency.
The accepted native evidence source remains
`04dce604f6be75df064d40519187b482ceb4ddb8`.

External manifest pin:
`0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987`.
Rebuilt ZIP pin:
`4f78ba072f5b458231ba8ba394e25bc9fc953e2bf288f28e30682a4e7a5a3a60`.
The delivery record names ZIP
`fe5555954cc6596b478346a6df1ff1e3c78da9d01f16c9f73ce967407a9c0ece`,
whose bytes were not supplied here. The rebuilt archive is **not** reported as
that original ZIP. The externally pinned manifest and every payload byte do
match; no claim is made about why the container bytes differ.

Rebuild in a separate exact-source checkout and verify using the external pin:

```sh
python cases/simlox-air-support/handoff-v1/portable.py pack \
  --repo . --output /absolute/fresh/path/a01-a02.zip
python cases/simlox-air-support/handoff-v1/portable.py verify \
  --zip /absolute/fresh/path/a01-a02.zip \
  --manifest-sha256 0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987
```

`experiments.simlox_pairing.provenance.load_handoff` checks external pins before
running the exact pinned portable validator. Package integrity does not prove
native execution. The four original Windows evidence locations/hashes remain
unchanged references; this consumer does not rerun SIMLOX or reaccept GUI work.
