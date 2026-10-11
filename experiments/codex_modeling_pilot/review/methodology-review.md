# Methodology review

Read-only review by a separate inherited-model Codex agent; this is AI review, not human review. Conducted after input freeze without inspecting candidate submissions. No frozen inputs were changed as a result.

The reviewer found no execution-blocking issue requiring a mid-experiment change. Public `validate` does not import the evaluator, and final scoring re-executes candidates and verifies the input fingerprint.

Required interpretation limits:

- T07/T08 explicitly prescribe clarify/unsupported responses. Their scores measure compliance, not autonomous discovery. Field/keyword scoring needs separate semantic review, which was performed with group labels removed.
- Candidates are normalized bounded-model configurations. The existing importer/compiler constructs the IR; the experiment does not demonstrate open-ended mechanism discovery.
- Mechanism cards overlap substantially with the schema. A/B cannot isolate a compositional mechanism library or MCP benefit. C additionally changes feedback and compute opportunity.
- The evaluator implements strict task-specification matching, not general semantic equivalence.
- Replay covers stored candidate execution/scoring, not hosted generation. Shared filesystem, unknown exact model snapshot, one context per arm, and one sample per task limit inference.

These qualifications are preserved in the result report. All primary scores remain unchanged.
