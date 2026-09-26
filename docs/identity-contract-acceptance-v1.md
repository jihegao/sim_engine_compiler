# Identity foundation: finite acceptance v1

Task: `engine-identity-contract-595cb5e-v1`, 2026-09-27.
Base: `595cb5eee9987324b19a8c3566f201f937e05f15`.
Scope: Python offline artifact/bundle and run/sample/event identity APIs, CLI,
versioned reports, persisted B1/F35 fixtures and adversarial controls.

## Results

| Check | Result |
|---|---|
| Frozen full Python suite, `PYTHONPATH=src .venv/bin/python -m pytest -q` | 242 passed, 14 skipped, 101.02 seconds |
| Identity contract suite, `tests/conformance/test_identity*.py` | 94 passed |
| Existing IR layers + ABM/runtime source-semantics targeted suite | 49 passed |
| Existing aircraft Rust runtime + event-time differential suite | 16 passed |
| Ruff, all new identity code/tests | Passed |
| Documentation local links, fixture input/artifact hashes, independent layer reload | Passed |
| Independent review and hostile-input controls | Passed; no remaining blocker |

Targeted results overlap the full suite; they are not additional independent
samples. Local skips are optional native/MLIR integration prerequisites and are
not acceptance evidence for those paths. The unchanged base has successful
[main CI 36271508735](https://github.com/jihegao/sim_engine_compiler/actions/runs/36271508735),
but that is not the new PR's CI result. New-PR CI status must be read separately.

Environment: Python 3.12.13, pytest 8.4.2, SimPy 4.1.1; existing differential
checks invoke the Rust runtime. No new Rust implementation or formal performance
measurement is part of this acceptance.

## Evidence and acceptance boundary

The [independent review receipt](identity-contract-review-v1.json) binds the
implementation, contract documentation, fixture manifest and negative controls
by SHA-256. The [fixture manifest](../tests/fixtures/identity_contract/manifest.json)
binds the original canonical file and every persisted Business/Core/Plan/lineage
artifact. Tests inspect the persisted layers rather than relying on an importer
holding hidden canonical state. Existing Plan, compiler lowering, Rust runtime,
RNG and observation implementations are unchanged by this slice.

The new boundary rejects cross-revision associations even when an attacker
recomputes checksums. It preserves stable IDs through layout changes without
claiming that changed execution order is semantically equivalent. Run/sample
identity distinguishes repeated seeds, event references retain original
sequence, and missing/filtered/truncated evidence cannot be upgraded to a
complete explanation by changing report status or recomputing a digest.

Limitations are contractual, not silently accepted: indexed Plans are
unsupported by identity v1 because semantic Plan fingerprints exclude their
resource index; ABM/production mapping and native Rust identity APIs are not
implemented; coarse operations remain partially mapped; content hashes are not
authenticated execution provenance. Recorded rule/entity/source strings do not
establish a complete event-to-design mapping or causal explanation.

Issues #10 and #11 remain open for design export and runtime collection/query.
No SysML renderer, Cloud service/UI, new scheduler or collection default was
added. No SIMLOX mismatch was treated as an engine defect. PR #19/#16/#15 and
historical measurements were not merged or rewritten by this task.
