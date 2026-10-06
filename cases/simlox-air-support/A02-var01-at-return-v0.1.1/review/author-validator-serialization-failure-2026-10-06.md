# Read-only author validator output failure

The first postrun invocation of frozen `validate_native_cli.py` on run
`a02-var01-at-return-v011-ssh-20261006-01` exited 1 before writing its JSON
result. `run_checks()` produced the result, but `json.dumps()` raised
`TypeError: Object of type set is not JSON serializable`. The cause is the
`A01 run IDs` and `A02 run IDs` checks, whose actual and expected values are
Python sets. No native command was repeated, and no run file was changed.

The frozen checker SHA-256 is
`c7c18335011206d253c90f0b6efe842c6102cc7aedf8817f527953d83e6085b9`.
Direct read-only `run_checks()` inspection returned 4,209 checks, zero failed.
`serialize_author_validation.py` verifies that exact checker SHA and converts
sets into sorted arrays for JSON output. It does not change the checks or
their pass criteria. The serialized author verdict is a postrun file and has
its own source and result hashes in the evidence index.
