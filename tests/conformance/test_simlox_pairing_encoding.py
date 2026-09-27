"""UTF-8 boundaries for the portable A01/A02 pairing evidence tools.

These controls model a strict cp936 default on Linux.  They are regression
evidence for explicit JSON encodings, not native Windows acceptance.
"""

from __future__ import annotations

import io
import json
import locale
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.simlox_pairing.run import _write

ROOT = Path(__file__).resolve().parents[2]
NON_ASCII_ARTIFACT = (
    ROOT / "experiments/simlox_pairing/evidence/v1/negative-controls.json"
)
ORIGINAL_MODULES = (
    "tests.conformance.test_simlox_pairing_canonical",
    "tests.conformance.test_simlox_pairing_observations",
    "tests.conformance.test_simlox_pairing_provenance",
    "tests.conformance.test_simlox_pairing_runner",
)


class _Cp936Default:
    """Replace only implicit/locale text encodings; explicit UTF-8 is intact."""

    def __init__(self):
        self._real_open = io.open
        self._stack = None

    def _open(
        self,
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        if "b" not in mode:
            if errors not in (None, "strict"):
                raise AssertionError("text boundaries must not hide decoding errors")
            if encoding in (None, "locale"):
                encoding = "cp936"
        return self._real_open(
            file,
            mode,
            buffering,
            encoding,
            errors,
            newline,
            closefd,
            opener,
        )

    @staticmethod
    def _text_encoding(encoding, stacklevel=2):
        del stacklevel
        return "locale" if encoding is None else encoding

    def __enter__(self):
        from contextlib import ExitStack

        self._stack = ExitStack()
        self._stack.enter_context(
            patch("io.text_encoding", new=self._text_encoding)
        )
        self._stack.enter_context(patch("io.open", new=self._open))
        self._stack.enter_context(
            patch("locale.getpreferredencoding", return_value="cp936")
        )
        if hasattr(locale, "getencoding"):
            self._stack.enter_context(patch("locale.getencoding", return_value="cp936"))
        return self

    def __exit__(self, *exc_info):
        assert self._stack is not None
        return self._stack.__exit__(*exc_info)


class SimloxPairingEncodingTests(unittest.TestCase):
    def test_actual_non_ascii_artifact_exposes_legacy_implicit_cp936_read(self):
        raw = NON_ASCII_ARTIFACT.read_bytes()
        self.assertIn(bytes("周剖面", "utf-8"), raw)

        with _Cp936Default():
            self.assertEqual(locale.getpreferredencoding(False), "cp936")
            with self.assertRaises(UnicodeDecodeError):
                NON_ASCII_ARTIFACT.read_text()
            with self.assertRaisesRegex(AssertionError, "must not hide"):
                NON_ASCII_ARTIFACT.read_text(encoding="utf-8", errors="ignore")

        parsed = json.loads(NON_ASCII_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(
            parsed["controls"][0]["changed_canonical"]["mission_profile"][
                "periodic_source"
            ]["label"],
            "周剖面",
        )

    def test_explicit_utf8_writer_round_trips_non_ascii_under_cp936_default(self):
        value = {
            "schema": "encoding-regression/v1",
            "label": "周剖面",
            "note": "飞机配对",
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evidence.json"
            with _Cp936Default():
                _write(target, value)
                raw = target.read_bytes()
                decoded = json.loads(raw.decode("utf-8"))
                with self.assertRaises(UnicodeDecodeError):
                    target.read_text()

        self.assertEqual(decoded, value)
        self.assertIn(bytes("飞机配对", "utf-8"), raw)

    def test_original_32_regressions_pass_with_utf8_mode_off_and_cp936_default(self):
        sitecustomize = textwrap.dedent(
            """
            import io
            import locale

            _real_open = io.open

            def _cp936_text_encoding(encoding, stacklevel=2):
                del stacklevel
                return "locale" if encoding is None else encoding

            def _cp936_open(file, mode="r", buffering=-1, encoding=None, errors=None,
                            newline=None, closefd=True, opener=None):
                if "b" not in mode:
                    if errors not in (None, "strict"):
                        raise AssertionError("text boundaries must not hide decoding errors")
                    if encoding in (None, "locale"):
                        encoding = "cp936"
                return _real_open(file, mode, buffering, encoding, errors, newline,
                                  closefd, opener)

            io.text_encoding = _cp936_text_encoding
            io.open = _cp936_open
            locale.getpreferredencoding = lambda do_setlocale=True: "cp936"
            if hasattr(locale, "getencoding"):
                locale.getencoding = lambda: "cp936"
            """
        )
        bootstrap = textwrap.dedent(
            f"""
            import json
            import locale
            import sys
            import unittest

            modules = {ORIGINAL_MODULES!r}
            suite = unittest.TestSuite()
            counts = {{}}
            for module in modules:
                loaded = unittest.defaultTestLoader.loadTestsFromName(module)
                counts[module] = loaded.countTestCases()
                suite.addTests(loaded)
            result = unittest.TextTestRunner(verbosity=1).run(suite)
            payload = {{
                "utf8_mode": sys.flags.utf8_mode,
                "preferred_encoding": locale.getpreferredencoding(False),
                "collected": sum(counts.values()),
                "executed": result.testsRun,
                "skipped": len(result.skipped),
                "failures": len(result.failures),
                "errors": len(result.errors),
                "successful": result.wasSuccessful(),
            }}
            print("CP936_RESULT=" + json.dumps(payload, sort_keys=True))
            raise SystemExit(0 if payload["successful"] and not payload["skipped"]
                             and payload["collected"] == payload["executed"] == 32 else 1)
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            hook = Path(directory) / "sitecustomize.py"
            hook.write_text(sitecustomize, encoding="utf-8")
            environment = os.environ.copy()
            environment.pop("PYTHONUTF8", None)
            environment.pop("PYTHONIOENCODING", None)
            environment["PYTHONPATH"] = os.pathsep.join(
                (directory, str(ROOT / "src"), str(ROOT))
            )
            completed = subprocess.run(
                [sys.executable, "-X", "utf8=0", "-c", bootstrap],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=180,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        marker = next(
            line.removeprefix("CP936_RESULT=")
            for line in completed.stdout.splitlines()
            if line.startswith("CP936_RESULT=")
        )
        result = json.loads(marker)
        self.assertEqual(result["utf8_mode"], 0)
        self.assertEqual(result["preferred_encoding"].lower(), "cp936")
        self.assertEqual(result["collected"], 32)
        self.assertEqual(result["executed"], 32)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["errors"], 0)


if __name__ == "__main__":
    unittest.main()
