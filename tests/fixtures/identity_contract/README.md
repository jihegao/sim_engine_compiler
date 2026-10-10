# Public identity contract fixtures

These are persisted aircraft Business v1, Core v2, Plan v1alpha2 and
`compiler-lineage/v2` artifacts generated at compiler main
`595cb5eee9987324b19a8c3566f201f937e05f15`. `manifest.json` binds every
artifact file and the original canonical fixture file by SHA-256.

- `b1`: the existing hand-calculable `b1-daily-operations` fixture.
- `f35`: the existing F35 43-day canonical snapshot from upstream
  `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`.

Both use `legacy-minute-v1`. Identity tests load these persisted artifacts,
not an importer holding a hidden canonical document. The manifest regression
also checks independent Business-to-Core and Core-to-Plan reconstruction.
Fixture generation is not simulation acceptance or a new performance result.

To reproduce in a fresh directory using the pinned compiler:

```sh
PYTHONPATH=src .venv/bin/python scripts/compile_ir.py \
  tests/fixtures/synthetic/b1-daily-operations.json /tmp/identity-b1-plan.json \
  --artifacts-dir /tmp/identity-b1
PYTHONPATH=src .venv/bin/python scripts/compile_ir.py \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json \
  /tmp/identity-f35-plan.json --artifacts-dir /tmp/identity-f35
```

The temporary directories must be new. Do not regenerate committed evidence
in place to make a failing hash check pass. Mutated negative controls are made
from independent deep copies in tests; their new fingerprints do not establish
that an old Business or a different Plan belongs to the same bundle.
