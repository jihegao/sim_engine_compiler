import unittest

from validate_native_cli import parse_system_surp_tasks


class SystemSurpEventParserTests(unittest.TestCase):
    def test_nested_subtask_start_lines_are_not_system_task_events(self):
        lines = [
            "Time: 9.28145  system SURP task 0 on <TEACH-AIR-01,0> started",
            "Time: 9.28145  remove subitem subtask 0 seqno 0 within system SURP task 0 on <TEACH-AIR-01,0> started",
            "Time: 10.0314  fit subitem subtask 1 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started",
            "Time: 10.0314  remove subitem subtask 0 seqno 0 within system SURP task 0 on <TEACH-AIR-01,0> completed",
            "Time: 10.7814  system SURP task 0 on <TEACH-AIR-01,0> completed",
        ]
        self.assertEqual(
            {"0": {"started": 9.28145, "completed": 10.7814}},
            parse_system_surp_tasks(lines),
        )

    def test_duplicate_top_level_lifecycle_event_is_still_rejected(self):
        lines = [
            "Time: 9.0 system SURP task 0 on <TEACH-AIR-01,0> started",
            "Time: 9.1 system SURP task 0 on <TEACH-AIR-01,0> started",
        ]
        with self.assertRaisesRegex(SystemExit, "duplicate system SURP task started: 0"):
            parse_system_surp_tasks(lines)


if __name__ == "__main__":
    unittest.main()
