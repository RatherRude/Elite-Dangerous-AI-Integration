from pathlib import Path
import runpy
from types import SimpleNamespace

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


def test_chat_has_no_production_ocr_smoke_entrypoint() -> None:
    source = (ROOT_DIR / "src" / "Chat.py").read_text(encoding="utf-8")
    assert "--ocr-smoke-test" not in source
    assert "OcrSmokeTest" not in source
    assert not (ROOT_DIR / "src" / "lib" / "OcrSmokeTest.py").exists()


def test_workflows_have_no_extra_ocr_jobs_or_release_gates() -> None:
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
