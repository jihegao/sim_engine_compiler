# Historical v1 hot records

These immutable records predate the serialization-timer correction.
`serialize_ns` includes both sample-only and complete-result serialization;
it is not the cost of serializing one complete output. `run_ns` was measured
separately and is unaffected. Use the corrected [v2 records](../hot-v2/records.json)
and the parent [report](../REPORT.md) for the current J35 hot experiment.
