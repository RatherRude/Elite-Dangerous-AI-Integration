from __future__ import annotations
import json, zipfile, datetime, platform, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INCLUDE_PATHS: list[str | Path] = []
AUTO_INCLUDE_LOG = True
LOG_CANDIDATES = [
    ROOT / "logs" / "com.covas-next.ui.log",
    Path.home() / ".config" / "com.covas-next.ui" / "logs" / "com.covas-next.ui.log",
    Path.home() / ".var" / "app" / "com.covas-next.ui" / "data" / "com.covas-next.ui" / "logs" / "com.covas-next.ui.log",
    Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "com.covas-next.ui" / "logs" / "com.covas-next.ui.log",
    Path.home() / "Library" / "Logs" / "com.covas-next.ui" / "com.covas-next.ui.log",
]

def _ts(): return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _norm_list(xs):
    out = []
    for x in xs or []:
        p = x if isinstance(x, Path) else Path(str(x))
        p = p.expanduser()
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        out.append(p)
    return out

def _add_include(tmp: Path, include: list[Path]):
    for src in include or []:
        if src.is_file():
            (tmp / src.name).write_bytes(src.read_bytes())
        elif src.is_dir():
            for f in src.rglob("*"):
                if f.is_file():
                    rel = f"{src.name}-{f.relative_to(src)}".replace("\\","_").replace("/","_")
                    (tmp / rel).write_bytes(f.read_bytes())

def create_bug_report() -> str:
    out_dir = (ROOT / "bugreports").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"BugReport_{_ts()}.zip"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        info = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "os": platform.platform(),
            "python": platform.python_version(),
        }
        (tmp / "system_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        (tmp / "README.txt").write_text("COVAS:NEXT local bug report.\n", encoding="utf-8")
        if AUTO_INCLUDE_LOG:
            for c in LOG_CANDIDATES:
                if c.is_file():
                    (tmp / "com.covas-next.ui.log").write_bytes(c.read_bytes())
                    break
        _add_include(tmp, _norm_list(INCLUDE_PATHS))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in tmp.rglob("*"):
                zf.write(f, f.name)
    return str(zip_path)

if __name__ == "__main__":
    print(create_bug_report())
