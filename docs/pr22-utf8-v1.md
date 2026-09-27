# PR22 default-locale UTF-8 repair v1

Task `engine-pr22-utf8-and-issue6-baseline-v1`, slice A. Starting consumer head:
`5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe`. This is a test/consumer encoding fix,
not a simulation semantics repair. The final fixed commit is pinned in the PR22
handoff comment and exact-head CI; do not substitute a moving branch for that pin.

## Actual failure retained

The original Windows receipt is retained unchanged at PR21
`d39e9c69267d570ca9518ff693a7f27a1d0a4776`:
`cases/simlox-air-support/windows-retest-5289fb5-v1/receipt.json`, SHA-256
`08b2f20cbbc520561e8edc27fa48567e70d2160d77da554c4fd8d8410666e147`.
On 4700-3 / Windows 10 / Python3.12.14 / SimPy4.1.1, the original default-GBK
command collected32, passed31, errored1, skipped0. The first error was an
implicit `Path.read_text()` of UTF-8 `negative-controls.json` at runner test
line21. Its actual non-ASCII `周剖面` text is not valid as that GBK byte stream.
The historical `PYTHONUTF8=1` ordinary/LF/CRLF runs each passed32; they remain
conditional successes, not evidence of a default-locale pass.

## Repair and audit

- Both runner-test JSON reads now specify `encoding="utf-8"`.
- Pairing consumer JSON digest encoding, Git stdout/stderr decoding and the
  manifest/expected/template/contract ZIP JSON boundaries explicitly select UTF-8.
  Python's former argument-free byte encode/decode already defaulted to UTF-8;
  spelling it out makes this boundary auditable, not a semantic change.
- The evidence writer already selected UTF-8 and still preserves non-ASCII JSON.
- The required test collector includes the encoding module. It rejects skipped,
  missing, failed and expected-failed cases rather than hiding a decoding error.
- Binary evidence and source hashes continue to use exact bytes. The strict
  Git-blob-or-whole-file-LF-to-CRLF policy and all historical receipts are unchanged.

The three new tests use the real non-ASCII artifact, round-trip non-ASCII values
through the real writer, and run all original32 tests in a subprocess with
`-X utf8=0` and a scoped modeled cp936 default. The harness redirects only
implicit/locale file encodings to cp936; explicit UTF-8 remains intact. It also
asserts that the old implicit read raises `UnicodeDecodeError` and that ignoring
decode errors is rejected. No `PYTHONUTF8` or `PYTHONIOENCODING` override masks
the file boundary. The parent fixture models implicit encoding independently of
the outer interpreter's UTF-8 mode.

The only pre-existing lossy decode is Git *error diagnostic* text with
`errors="replace"`; it is not used to parse or authenticate JSON/source bytes.
No JSON decode ignores or replaces errors. Broader engine APIs, including
`native.py`, are outside this bounded repair and remain unchanged.

These are Linux regression controls modelling a Windows encoding boundary.
They do **not** constitute a new native 4700-3 default-locale acceptance.

## Frozen pairing identities (unchanged)

| Identity | Value |
| --- | --- |
| Engine baseline | `595cb5eee9987324b19a8c3566f201f937e05f15` |
| Canonical POSIX source build fingerprint (26 files) | `8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1` |
| A01 canonical digest | `1ebd4dd38540385db50d94c4113b42b9e63f30843fad5c294ff00134d2306c4f` |
| A01 Plan fingerprint | `806837849521ca00708fb2f85bcc3b2b72e2bfaa87d846d528f19d356f36e2b6` |
| A02 canonical digest | `ac42f4c657dc205c1b9c3f7684008d53110d2af191e9d4313da4dc2fd45b19df` |
| A02 Plan fingerprint | `8fe2564e61815d0fe683c2ee476037f86a64a4a73b2d18148fcd7c349505402e` |
| Native external manifest | `0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987` |
| Revised consumer LF source fingerprint | `4bea3aca63963c7192c5895627bdf29dc3b6acdf0595fbe92943ad0d8e802aa8` |

Consumer code and tests intentionally changed, while the engine build pin did
not. Windows CRLF executed-source/consumer fingerprints may differ from LF;
record them separately, do not equate normalized source identity with file-byte
identity. The existing strict newline gate remains the authority.

Fresh Linux checks: 35/35 required tests, zero skips; A01 625 and A02 681 mapped
checks, 72 bins each, four semantic negative controls passed, first mapped
discrepancy null. Provenance negative controls remain in the original test set.
Raw generated evidence is in the new ignored `runs/pr22-utf8-v1/fresh-pairing/`
directory and in exact-head dedicated CI artifacts, not copied over historical
`experiments/simlox_pairing/evidence/v1/`.

## Native Windows handoff — coordinator only

The unique 4700-3 coordinator should use fresh ordinary/default, controlled LF
and controlled CRLF checkouts of the exact fixed commit from the PR22 comment.
Ensure the pinned engine baseline Git object exists; fetch that object explicitly
if the checkout is shallow. Do not replace it with HEAD or a nearby revision.
Use Python3.12 + SimPy4.1.1 as before, preserving all old failing/conditional
receipts and running no native SIMLOX/GUI/performance work in this test slice.

In each isolated checkout, set only the local process `PYTHONPATH=src` and
optionally `PYTHONDONTWRITEBYTECODE=1`. Remove any process-level `PYTHONUTF8`
and `PYTHONIOENCODING` overrides inherited from the previous conditional run;
do not change machine locale/registry/system environment. Verify and retain:

```powershell
git rev-parse HEAD
git config --show-origin --get core.autocrlf
python -c "import json,locale,sys; print(json.dumps({'python':sys.version,'utf8_mode':sys.flags.utf8_mode,'encoding':locale.getencoding()})); assert sys.flags.utf8_mode == 0; assert locale.getencoding().lower() in ('cp936','gbk','936')"
python -m experiments.simlox_pairing.check_tests
python -m experiments.simlox_pairing.run --output C:\path\to\fresh-nonexistent-evidence
```

The unmodified outer command should execute35 tests, with no error/failure/skip.
The encoding module also reruns the original32 under its scoped model, but that
inner model does not replace the outer real default-locale result. If the
environment is not default GBK, record that fact and stop rather than forcing a
UTF-8 success. The output path must be newly named for each checkout mode.

Retain source fingerprints, per-case canonical/Plan/result hashes, all25 JSON
artifacts and the evidence index, comparison counts, four semantic controls,
provenance negative-control results, stdout/stderr and exit codes. Require the
same 625/681 checks and72 bins, unchanged input/Plan/build pins and zero mapped
discrepancies. Cross-mode raw file hashes may differ because of newlines.
This agent does not launch or manage that Windows session.

No runtime/RNG/default path, fixtures, legacy evidence, GUI status or scope of
SIMLOX equivalence changed. PR22 stays Draft; no merge or issue closure.
