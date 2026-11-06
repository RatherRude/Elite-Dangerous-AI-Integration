import json
from pathlib import Path
import subprocess
import sys
import tempfile


def test_rapidocr_artifact(chat_dir: Path) -> None:
    chat_dir = chat_dir.resolve()
    package_dir = chat_dir / "_internal" / "rapidocr_onnxruntime"
    if not (package_dir / "config.yaml").is_file():
        raise FileNotFoundError(package_dir / "config.yaml")
    if len(list((package_dir / "models").glob("*.onnx"))) < 3:
        raise RuntimeError(f"RapidOCR models are missing from {package_dir}")
    executable = chat_dir / ("Chat.exe" if sys.platform == "win32" else "Chat")
    with tempfile.TemporaryDirectory() as working_dir:
        result = subprocess.run(
            [str(executable), "--ocr-smoke-test"], cwd=working_dir,
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"RapidOCR artifact smoke test exited with {result.returncode}")
    reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    report = next((report for report in reports if report.get("ocr_smoke_test") == "passed"), None)
    if report is None:
        raise RuntimeError("RapidOCR artifact smoke test did not report success")
    if report.get("frozen") is not True or Path(report.get("package_dir", "")).resolve() != package_dir:
        raise RuntimeError("RapidOCR was not loaded from the packaged executable")


if __name__ == "__main__":
    test_rapidocr_artifact(Path(sys.argv[1]))
