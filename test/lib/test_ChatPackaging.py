from pathlib import Path, PurePosixPath
import runpy
import subprocess
import json
from types import SimpleNamespace

import pytest
import rapidocr_onnxruntime
import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_chat_spec_collects_rapidocr_config_and_all_configured_models() -> None:
    collected_data = []

    def fake_analysis(*args, **kwargs):
        collected_data.extend(kwargs["datas"])
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=kwargs["datas"])

    runpy.run_path(str(ROOT_DIR / "Chat.spec"), init_globals={
        "Analysis": fake_analysis,
        "PYZ": lambda *args, **kwargs: None,
        "EXE": lambda *args, **kwargs: None,
        "COLLECT": lambda *args, **kwargs: None,
    })

    package_dir = Path(rapidocr_onnxruntime.__file__).resolve().parent
    config = yaml.safe_load((package_dir / "config.yaml").read_text(encoding="utf-8"))
    required_files = [Path("config.yaml")] + [Path(config[section]["model_path"]) for section in ("Det", "Cls", "Rec")]
    bundled_files = {
        Path(destination) / Path(source).name: Path(source).resolve()
        for source, destination in collected_data
    }
    for relative_path in required_files:
        assert bundled_files[Path("rapidocr_onnxruntime") / relative_path] == package_dir / relative_path
        assert (package_dir / relative_path).is_file()


@pytest.mark.parametrize("returncode", [0, 1])
def test_artifact_smoke_runs_bundled_executable_in_clean_directory(tmp_path, monkeypatch, returncode) -> None:
    artifact_dir = tmp_path / "Chat"
    package_dir = artifact_dir / "_internal" / "rapidocr_onnxruntime"
    models_dir = package_dir / "models"
    models_dir.mkdir(parents=True)
    (package_dir / "config.yaml").touch()
    for model_name in ("det", "cls", "rec"):
        (models_dir / f"{model_name}.onnx").touch()

    def fake_run(command, **kwargs):
        assert Path(command[0]).parent == artifact_dir
        assert command[1:] == ["--ocr-smoke-test"]
        assert list(Path(kwargs["cwd"]).iterdir()) == []
        assert Path(kwargs["cwd"]) != artifact_dir
        assert kwargs["timeout"] == 120
        report = {"ocr_smoke_test": "passed", "frozen": True, "package_dir": str(package_dir)}
        return subprocess.CompletedProcess(command, returncode, json.dumps(report) + '\n', '')

    monkeypatch.setattr(subprocess, "run", fake_run)
    smoke_test = runpy.run_path(str(ROOT_DIR / "e2e" / "test_RapidOCRArtifact.py"))["test_rapidocr_artifact"]
    if returncode:
        with pytest.raises(RuntimeError, match="exited with 1"):
            smoke_test(artifact_dir)
    else:
        smoke_test(artifact_dir)


@pytest.mark.parametrize("failure", [None, "source", "host_models", "process"])
def test_flatpak_smoke_requires_frozen_bundled_ocr(monkeypatch, failure) -> None:
    package_dir = PurePosixPath("/app/bin/resources/Chat/_internal/rapidocr_onnxruntime")
    report = {
        "ocr_smoke_test": "passed", "frozen": failure != "source",
        "package_dir": str(package_dir),
        "models": [str(package_dir / "models" / f"{name}.onnx") for name in ("det", "cls", "rec")],
    }
    if failure == "host_models":
        report["models"][0] = "/usr/lib/python3/site-packages/rapidocr_onnxruntime/models/det.onnx"

    def fake_run(command, **kwargs):
        assert command[:4] == ["flatpak", "run", "--user", "--unshare=network"]
        assert "--nofilesystem=host:reset" in command
        assert "com.covasnext.ui" in command
        assert "/app/bin/resources/Chat/Chat --ocr-smoke-test" in command[-1]
        assert list(Path(kwargs["cwd"]).iterdir()) == []
        return subprocess.CompletedProcess(command, 1 if failure == "process" else 0, json.dumps(report) + '\n', '')

    monkeypatch.setattr(subprocess, "run", fake_run)
    smoke_test = runpy.run_path(str(ROOT_DIR / "e2e" / "test_RapidOCRFlatpak.py"))["test_rapidocr_flatpak"]
    if failure:
        with pytest.raises(RuntimeError):
            smoke_test()
    else:
        smoke_test()


def test_artifact_smoke_tests_remain_manual_without_extra_ci_jobs_or_release_gates() -> None:
    for workflow_name, release_dependencies in (
        ("build-executable.yml", ["electron-build", "e2e"]),
        ("build-executable-linux.yml", ["flatpak-bundle", "e2e"]),
    ):
        workflow = yaml.load((ROOT_DIR / ".github" / "workflows" / workflow_name).read_text(), Loader=yaml.BaseLoader)
        assert workflow["on"] == ["push", "pull_request"]
        assert workflow["permissions"] == {"contents": "read"}
        assert "dir-ocr-smoke" not in workflow["jobs"]
        assert "flatpak-ocr-smoke" not in workflow["jobs"]
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                assert "test_RapidOCRArtifact.py" not in step.get("run", "")
                assert "test_RapidOCRFlatpak.py" not in step.get("run", "")
        release = workflow["jobs"]["draft-release"]
        assert release["needs"] == release_dependencies
        assert release["if"] == "startsWith(github.ref, 'refs/tags/')"
