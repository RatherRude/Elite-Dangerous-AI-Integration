import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.timeout(120)
def test_chat_ocr_smoke_test_runs_inference_from_clean_working_directory(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "src" / "Chat.py"), "--ocr-smoke-test"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ocr_smoke_test"] == "passed"
    assert report["frozen"] is False
    assert len(report["models"]) == 3
    assert "COVASNEXT323" in "".join(report["text"].upper().split())
    assert list(tmp_path.iterdir()) == []
