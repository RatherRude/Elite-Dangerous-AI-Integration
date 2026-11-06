import json
import sys
from pathlib import Path


def run_ocr_smoke_test() -> None:
    import cv2
    import numpy as np
    import rapidocr_onnxruntime
    import yaml
    from rapidocr_onnxruntime import RapidOCR

    package_dir = Path(rapidocr_onnxruntime.__file__).resolve().parent
    config_path = package_dir / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model_paths = []
    for section in ("Det", "Cls", "Rec"):
        model_path = package_dir / config[section]["model_path"]
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        model_paths.append(str(model_path))

    image = np.full((160, 720, 3), 255, dtype=np.uint8)
    cv2.putText(image, "COVAS NEXT 323", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    engine = RapidOCR()
    results, _ = engine(image, use_cls=True)
    text = " ".join(result[1] for result in (results or []))
    if "COVASNEXT323" not in "".join(text.upper().split()):
        raise RuntimeError(f"RapidOCR smoke test did not recognize the test image: {text!r}")
    print(json.dumps({
        "ocr_smoke_test": "passed", "text": text,
        "frozen": bool(getattr(sys, "frozen", False)),
        "package_dir": str(package_dir), "models": model_paths,
    }), flush=True)
