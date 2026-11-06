import json
from pathlib import PurePosixPath
import subprocess
import tempfile


def test_rapidocr_flatpak() -> None:
    package_dir = PurePosixPath("/app/bin/resources/Chat/_internal/rapidocr_onnxruntime")
    command = [
        "flatpak", "run", "--user", "--unshare=network", "--nofilesystem=host:reset",
        "--nosocket=session-bus", "--nosocket=system-bus", "--nosocket=x11",
        "--nosocket=pulseaudio", "--nodevice=all", "--command=sh", "com.covasnext.ui",
        "-c", 'set -eu; workdir="$(mktemp -d)"; trap \'rm -rf "$workdir"\' EXIT; '
        'cd "$workdir"; /app/bin/resources/Chat/Chat --ocr-smoke-test',
    ]
    with tempfile.TemporaryDirectory() as working_dir:
        result = subprocess.run(command, cwd=working_dir, capture_output=True, text=True, encoding="utf-8", timeout=120)
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Flatpak RapidOCR smoke test exited with {result.returncode}")
    reports = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    report = next((report for report in reports if report.get("ocr_smoke_test") == "passed"), None)
    if report is None or report.get("frozen") is not True or report.get("package_dir") != str(package_dir):
        raise RuntimeError("RapidOCR did not run from the installed Flatpak executable")
    models = report.get("models", [])
    if len(models) != 3 or any(PurePosixPath(model).parent != package_dir / "models" for model in models):
        raise RuntimeError("RapidOCR did not load all three models from the Flatpak")


if __name__ == "__main__":
    test_rapidocr_flatpak()
