import subprocess
import sys
from pathlib import Path


REDTEAM_SCRIPT_EXPECTATIONS = {
    "redteam_exp.py": ("iou=", "tmp:"),
    "redteam_exp2.py": ("iou=", "tmp:"),
    "redteam_exp3.py": (
        "wrong-color candidate vs black baseline",
        "gated_failures:",
        "trust in row:",
        "comparable in row:",
        "tmp:",
    ),
}


def test_redteam_experiments_run_with_current_output_shape():
    root = Path(__file__).resolve().parents[1]
    for script, expected_markers in REDTEAM_SCRIPT_EXPECTATIONS.items():
        result = subprocess.run(
            [sys.executable, str(root / script)],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        for marker in expected_markers:
            assert marker in result.stdout
