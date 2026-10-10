"""Owned-process fixtures: stdlib mocks and tiny Python children, no engine runs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from benchmarks.three_arm_v1 import driver


ROOT = Path(__file__).resolve().parents[2]


def _exited_process():
    process = Mock(pid=987654, returncode=0)
    process.poll.return_value = 0
    process.wait.return_value = 0
    return process


CANCELLATION_FIXTURE = r'''
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from unittest.mock import patch
from benchmarks.three_arm_v1 import driver

base = Path(sys.argv[1])
mode = sys.argv[2]
signum = int(sys.argv[3])
real_popen = subprocess.Popen
real_killpg = os.killpg
launches = []
injected = False
prior = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

def launch(command, **kwargs):
    process = real_popen([sys.executable, '-c', 'import time; time.sleep(15)'], **kwargs)
    launches.append(process.pid)
    (base / 'owned.pid').write_text(str(process.pid))
    if mode in ('startup', 'measure-startup'):
        os.kill(os.getpid(), signum)
    return process

def overlap():
    global injected
    if mode == 'running' and not injected:
        injected = True
        os.kill(os.getpid(), signum)
    return []

def killpg(pgid, sig):
    global injected
    result = real_killpg(pgid, sig)
    trigger = (mode == 'cleanup-entry' and sig == 0) or (
        mode == 'cleanup-late' and sig == signal.SIGKILL)
    if trigger and not injected:
        injected = True
        for delivered in (signum, signal.SIGINT, signal.SIGTERM, signum):
            os.kill(os.getpid(), delivered)
    return result

with patch.object(driver.subprocess, 'Popen', side_effect=launch), patch.object(
    driver.os, 'killpg', side_effect=killpg
):
    if mode == 'measure-startup':
        run_dir = base / 'run'
        run_dir.mkdir()
        (run_dir / 'manifest.json').write_text('{}')
        manifest = {
            'protocol': {'max_normalized_load': 0.05},
            'schedule': [{'ordinal': index, 'case_id': 'tiny'} for index in range(2)]}
        quiet = {'hostname': driver.EXPECTED_HOST, 'normalized_load_1m': 0,
                 'process_affinity': list(range(8)), 'heavy_processes': []}
        with patch.object(driver, '_load_frozen', return_value=manifest), patch.object(
            driver, '_validate_frozen_files'
        ), patch.object(driver, 'machine_snapshot', return_value=quiet), patch.object(
            driver, 'heavy_processes', return_value=[]
        ), patch.object(driver, '_cell_command', return_value=[sys.executable, '-c', 'pass']):
            try:
                driver.measure(argparse.Namespace(run_dir=run_dir, deadline_seconds=1200))
            except driver.CellFailure:
                pass
        state = json.loads((run_dir / 'state.json').read_text())
        failure = json.loads((run_dir / 'measurement/cell-000/record.json').read_text())
        assert state['status'] == 'incomplete' and state['cells_completed'] == 0
        assert state['interrupted'] and failure['status'] == 'failed'
        assert not (run_dir / 'measurement/cell-001').exists()
        execution = failure['execution']
    else:
        try:
            driver._run_capture([sys.executable, '-c', 'pass'],
                timeout=0.05 if mode.startswith('cleanup-') else 5,
                overlap_check=overlap, environment={})
        except driver.CellFailure as error:
            assert error.reason == 'coordinator_interrupt:CoordinatorInterrupted'
            execution = error.execution
        else:
            raise AssertionError('cancelled child was accepted')
assert len(launches) == 1
assert all(signal.getsignal(sig) == handler for sig, handler in prior.items())
(base / 'execution.json').write_text(json.dumps(execution))
'''


class ThreeArmLifecycleTests(unittest.TestCase):
    def _capture(self, command, *, timeout=2, overlap_check=lambda: []):
        return driver._run_capture(
            command, timeout=timeout, overlap_check=overlap_check, environment={}
        )

    def test_startup_error_preserves_execution_and_restores_signal_mask(self):
        before = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        with patch.object(driver.subprocess, "Popen", side_effect=FileNotFoundError("missing")):
            with self.assertRaisesRegex(driver.CellFailure, "cell_error:FileNotFoundError") as caught:
                self._capture(["missing"])
        execution = caught.exception.execution
        self.assertFalse(execution["process_started"])
        self.assertIsNone(execution["pid"])
        self.assertFalse(execution["completion_unknown"])
        self.assertEqual(execution["error"]["type"], "FileNotFoundError")
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), before)
        self.assertTrue(all(signal.getsignal(sig) == handler for sig, handler in handlers.items()))

    def test_finished_leader_cannot_hide_expired_startup_allowance(self):
        clock = [0.0]
        process = _exited_process()

        def launch(*args, **kwargs):
            clock[0] = 31.0
            return process

        with patch.object(driver.time, "monotonic", side_effect=lambda: clock[0]), patch.object(
            driver.subprocess, "Popen", side_effect=launch
        ), patch.object(driver.os, "killpg", side_effect=ProcessLookupError):
            with self.assertRaisesRegex(driver.CellFailure, "cell_timeout") as caught:
                self._capture(["synthetic"], timeout=30)
        self.assertTrue(caught.exception.execution["timed_out"])
        self.assertTrue(caught.exception.execution["child_reaped"])
        self.assertFalse(caught.exception.execution["completion_unknown"])

    def test_delayed_wait_return_cannot_pass_after_original_deadline(self):
        clock = [0.0]
        process = _exited_process()
        process.returncode = None
        process.poll.side_effect = lambda: process.returncode

        def wait(*args, **kwargs):
            process.returncode = 0
            clock[0] = 31.0
            return 0

        process.wait.side_effect = wait
        with patch.object(driver.time, "monotonic", side_effect=lambda: clock[0]), patch.object(
            driver.subprocess, "Popen", return_value=process
        ), patch.object(driver.os, "killpg", side_effect=ProcessLookupError):
            with self.assertRaisesRegex(driver.CellFailure, "cell_timeout"):
                self._capture(["synthetic"], timeout=30)

    def test_exited_leader_still_requires_orphan_group_cleanup(self):
        process = _exited_process()
        killed = []

        def killpg(pgid, sig):
            if sig == signal.SIGKILL:
                killed.append(pgid)
            elif killed:
                raise ProcessLookupError

        with patch.object(driver.subprocess, "Popen", return_value=process), patch.object(
            driver.os, "killpg", side_effect=killpg
        ):
            with self.assertRaisesRegex(driver.CellFailure, "surviving_owned_process_group") as caught:
                self._capture(["synthetic"])
        self.assertEqual(killed, [process.pid])
        self.assertTrue(caught.exception.execution["child_reaped"])
        self.assertTrue(caught.exception.execution["process_group_empty_after_wait"])
        self.assertFalse(caught.exception.execution["completion_unknown"])

    def test_leader_is_reaped_before_group_probe(self):
        process = _exited_process()
        reaped = []
        process.poll.side_effect = lambda: reaped.append(True) or 0

        def killpg(pgid, sig):
            self.assertTrue(reaped)
            raise ProcessLookupError

        with patch.object(driver.os, "killpg", side_effect=killpg):
            lifecycle = driver._terminate(process, timeout=0.01)
        self.assertFalse(lifecycle["completion_unknown"])

    def test_permission_denied_remains_unknown_after_later_empty_probe(self):
        for operation in ("probe", "kill"):
            with self.subTest(operation=operation):
                denied = []

                def killpg(pgid, sig):
                    if not denied and ((operation == "probe" and sig == 0) or (
                        operation == "kill" and sig == signal.SIGKILL
                    )):
                        denied.append(True)
                        raise PermissionError("denied")
                    if denied:
                        raise ProcessLookupError

                with patch.object(driver.os, "killpg", side_effect=killpg):
                    lifecycle = driver._terminate(_exited_process(), timeout=0.01)
                self.assertTrue(lifecycle["child_reaped"])
                self.assertTrue(lifecycle["process_group_empty_after_wait"])
                self.assertTrue(lifecycle["process_group_probe_unknown"])
                self.assertTrue(lifecycle["completion_unknown"])

    def test_live_group_cannot_be_accepted_with_reaped_leader(self):
        with patch.object(driver.os, "killpg"):
            lifecycle = driver._terminate(_exited_process(), timeout=0.01)
        self.assertTrue(lifecycle["child_reaped"])
        self.assertFalse(lifecycle["process_group_empty_after_wait"])
        self.assertTrue(lifecycle["completion_unknown"])

    def test_unknown_cleanup_rejects_and_preserves_primary_execution_error(self):
        for primary_error in (False, True):
            with self.subTest(primary_error=primary_error):
                process = _exited_process()
                probed = []
                if primary_error:
                    process.returncode = None
                    process.poll.side_effect = lambda: process.returncode

                def killpg(pgid, sig):
                    if sig == signal.SIGKILL:
                        process.returncode = 0
                    elif not probed:
                        probed.append(True)
                        raise PermissionError("cannot inspect owned group")
                    else:
                        raise ProcessLookupError

                def overlap():
                    raise ValueError("overlap admission unavailable")

                reason = "cell_error:ValueError" if primary_error else "owned_process_lifecycle_unknown"
                with patch.object(driver.subprocess, "Popen", return_value=process), patch.object(
                    driver.os, "killpg", side_effect=killpg
                ):
                    with self.assertRaisesRegex(driver.CellFailure, reason) as caught:
                        self._capture(["synthetic"], overlap_check=overlap)
                execution = caught.exception.execution
                self.assertTrue(execution["completion_unknown"])
                self.assertTrue(execution["child_reaped"])
                self.assertTrue(execution["process_group_empty_after_wait"])
                if primary_error:
                    self.assertEqual(execution["error"]["type"], "ValueError")

    def test_cleanup_never_signals_callers_process_group(self):
        process = _exited_process()
        process.pid = os.getpgrp()
        with patch.object(driver.os, "killpg") as killpg:
            lifecycle = driver._terminate(process, timeout=0.01)
        self.assertTrue(lifecycle["completion_unknown"])
        self.assertTrue(all(call.args[1] == 0 for call in killpg.call_args_list))

    def test_successful_tiny_child_unblocks_cancellation_signals(self):
        execution = self._capture([
            sys.executable, "-c",
            "import signal; print(sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK, set())))",
        ])
        blocked = json.loads(execution["stdout"])
        self.assertNotIn(int(signal.SIGINT), blocked)
        self.assertNotIn(int(signal.SIGTERM), blocked)
        self.assertTrue(execution["child_reaped"])
        self.assertTrue(execution["process_group_empty_after_wait"])
        self.assertFalse(execution["completion_unknown"])
        self.assertEqual(execution["exit_status"], 0)

    def test_timeout_and_foreign_overlap_kill_reap_and_record(self):
        for reason, overlap in (("cell_timeout", []), ("foreign_process_overlap", [{"pid": 1}])):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(driver.CellFailure, reason) as caught:
                    self._capture([sys.executable, "-c", "import time; time.sleep(15)"],
                                  timeout=0.05, overlap_check=lambda: overlap)
                execution = caught.exception.execution
                self.assertTrue(execution["child_reaped"])
                self.assertTrue(execution["process_group_empty_after_wait"])
                self.assertFalse(execution["completion_unknown"])
                self.assertEqual(execution["exit_status"], -signal.SIGKILL)

    def _cancel_fixture(self, mode, signum):
        with tempfile.TemporaryDirectory() as directory:
            # A different session must survive cleanup of the fixture's child.
            bystander = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(15)"], start_new_session=True
            )
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", CANCELLATION_FIXTURE, directory, mode, str(int(signum))],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=8, start_new_session=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                execution = json.loads((Path(directory) / "execution.json").read_text())
                self.assertTrue(execution["interrupted"])
                self.assertEqual(execution["interruption_signal"], signum)
                self.assertTrue(execution["child_reaped"])
                self.assertTrue(execution["process_group_empty_after_wait"])
                self.assertFalse(execution["completion_unknown"])
                self.assertGreaterEqual(execution["cancellation_count"], 4 if mode.startswith("cleanup-") else 1)
                with self.assertRaises(ProcessLookupError):
                    os.kill(execution["pid"], 0)
                with self.assertRaises(ProcessLookupError):
                    os.killpg(execution["pid"], 0)
                self.assertIsNone(bystander.poll())
            finally:
                owned = Path(directory) / "owned.pid"
                if owned.exists():
                    try:
                        os.killpg(int(owned.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                bystander.kill()
                bystander.wait(timeout=2)

    def test_running_cancellation_preserves_owned_cleanup(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                self._cancel_fixture("running", signum)

    def test_startup_cancellation_waits_for_process_ownership(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                self._cancel_fixture("startup", signum)

    def test_repeated_cleanup_signals_do_not_escape_cleanup(self):
        for mode in ("cleanup-entry", "cleanup-late"):
            with self.subTest(mode=mode):
                self._cancel_fixture(mode, signal.SIGTERM)

    def test_measure_startup_cancellation_archives_failure_without_next_launch(self):
        self._cancel_fixture("measure-startup", signal.SIGTERM)

    def test_late_measure_cancellation_keeps_execution_and_incomplete_state(self):
        import argparse

        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "manifest.json").write_text("{}")
            manifest = {"protocol": {"max_normalized_load": 0.05},
                        "schedule": [{"ordinal": index, "case_id": "tiny"} for index in range(2)]}
            quiet = {"hostname": driver.EXPECTED_HOST, "normalized_load_1m": 0,
                     "process_affinity": list(range(8)), "heavy_processes": []}
            real_write = driver._write_json
            captures = []

            def capture(command, **kwargs):
                captures.append(command)
                real_write(Path(command[0]), {})
                Path(command[1]).write_text("Maximum resident set size (kbytes): 1\n")
                return {"exit_status": 0, "child_reaped": True,
                        "process_group_empty_after_wait": True, "completion_unknown": False}

            def write(path, value):
                real_write(path, value)
                if path.name == "record.json" and value["status"] == "complete":
                    os.kill(os.getpid(), signal.SIGTERM)

            with patch.object(driver, "_load_frozen", return_value=manifest), patch.object(
                driver, "_validate_frozen_files"
            ), patch.object(driver, "machine_snapshot", return_value=quiet), patch.object(
                driver, "_cell_command", side_effect=lambda m, c, r, t: [str(r), str(t)]
            ), patch.object(driver, "_run_capture", side_effect=capture), patch.object(
                driver, "_verify_report", return_value="d" * 64
            ), patch.object(driver, "_write_json", side_effect=write):
                with self.assertRaises(driver.CoordinatorInterrupted):
                    driver.measure(argparse.Namespace(run_dir=run_dir, deadline_seconds=1200))
            state = json.loads((run_dir / "state.json").read_text())
            failure = json.loads((run_dir / "measurement/cell-000/record.json").read_text())
            self.assertEqual(len(captures), 1)
            self.assertEqual(state["status"], "incomplete")
            self.assertEqual(state["cells_completed"], 0)
            self.assertEqual(failure["status"], "failed")
            self.assertTrue(failure["execution"]["child_reaped"])
            self.assertTrue(failure["execution"]["interrupted"])
            self.assertFalse((run_dir / "measurement/cell-001").exists())


if __name__ == "__main__":
    unittest.main()
