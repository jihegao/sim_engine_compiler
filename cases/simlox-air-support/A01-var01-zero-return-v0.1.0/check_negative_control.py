"""Show that accepted A01 fails the zero-return task-completion gate."""
import hashlib
import json
from pathlib import Path

from validate_native_cli import PARENT_RUN, event_lines, timed

HERE = Path(__file__).resolve().parent
PARENT_LOG_SHA = "6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed"
OUTPUT = HERE / "review" / "negative-control-accepted-parent.json"

def main():
    path = PARENT_RUN / "model.log"
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha != PARENT_LOG_SHA:
        raise ValueError("accepted parent event log SHA differs")
    completions = [time for time, _ in timed(event_lines(path), "task completed: <TEACH-AIR-01,0>")]
    if completions != [9.5] or completions == [10.0]:
        raise ValueError(f"negative control no longer discriminates: {completions}")
    result = {"schema": "simlox-a01-var01-zero-return-v010-negative-control/v1",
              "parent_log_sha256": actual_sha, "accepted_parent_task_completion": completions,
              "predeclared_child_task_completion": [10.0], "child_gate_passed": False,
              "conclusion": "accepted parent fails child timing gate as required",
              "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUTPUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
