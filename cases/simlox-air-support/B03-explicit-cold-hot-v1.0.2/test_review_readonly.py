"""Mutation checks for the independent B03 raw-evidence reviewer.

The native acceptance run is intentionally not copied into source control.
Set B03_REVIEW_RUN to replay another sealed run locally.
"""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b03_review_readonly", HERE / "review_readonly.py")
assert spec and spec.loader
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)
RUN = Path(os.environ.get("B03_REVIEW_RUN", HERE / "runs" / "b03-v102-ssh-20260929-02"))


@unittest.skipUnless((RUN / "model.log").is_file() and (RUN / "report-raw.json").is_file(),
                     "sealed B03 native acceptance run is unavailable")
class ReviewerMutationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.log = (RUN / "model.log").read_text(encoding="utf-8-sig")
        cls.report = reviewer.read(RUN / "report-raw.json")
        assert not reviewer.assert_events(reviewer.event_rows(cls.log))
        assert not reviewer.check_report(cls.report)[0]

    def test_wrong_hot_step_duration_is_rejected(self) -> None:
        changed = self.log.replace(
            "subtask 2 seqno 1 within system preparation task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours",
            "subtask 2 seqno 1 within system preparation task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours",
            1,
        )
        self.assertNotEqual(changed, self.log)
        self.assertTrue(any("subtask" in e for e in reviewer.assert_events(reviewer.event_rows(changed))))

    def test_cross_recipe_work_is_rejected(self) -> None:
        extra = "Time: 11 subtask 4 seqno 2 within system preparation task 1 on <TEACH-AIR-01,0> started\n"
        changed = self.log.replace("Time: 11  system preparation task 1", extra + "Time: 11  system preparation task 1", 1)
        self.assertNotEqual(changed, self.log)
        self.assertTrue(any("subtask" in e for e in reviewer.assert_events(reviewer.event_rows(changed))))

    def test_stock_shortage_is_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        stock = next(t for t in changed["report"]["tables"] if t["name"] == "StockTotalResults")
        names = [column["name"] for column in stock["columns"]]
        stock["instances"][0]["rows"][0][names.index("NBO")] = 1
        self.assertTrue(any("StockTotalResults" in e for e in reviewer.check_report(changed)[0]))


if __name__ == "__main__":
    unittest.main()
