import subprocess
import sys
from pathlib import Path


def test_redteam_experiments_run_with_current_compare_result_fields():
    root = Path(__file__).resolve().parents[1]
    for script in ("redteam_exp.py", "redteam_exp2.py"):
        result = subprocess.run(
            [sys.executable, str(root / script)],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "iou=" in result.stdout
        assert "tmp:" in result.stdout
