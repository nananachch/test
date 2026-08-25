from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parent
WORK = Path(os.environ.get("RUNNER_TEMP", REPO / "_runner_temp")) / "csd_v024_build"
SOURCE = WORK / "source"
ARTIFACT = REPO / "build-artifact"
LOGS = ARTIFACT / "LOGS"
PLUGIN = ARTIFACT / "PLUGIN_FILES"
REPORTS = ARTIFACT / "REPORTS"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(ARTIFACT, ignore_errors=True)
    WORK.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    PLUGIN.mkdir(parents=True)
    REPORTS.mkdir(parents=True)

    chunk_dir = REPO / "chunks"
    chunks = sorted(chunk_dir.glob("source_v024_final.b64.*"))
    if not chunks:
        raise SystemExit("source payload chunks missing")
    archive = WORK / "source_v0.2.4.tar.gz"
    payload = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
    archive.write_bytes(base64.b64decode(payload))
    expected = (REPO / "source_v0.2.4.sha256").read_text(encoding="utf-8").split()[0]
    actual = sha256(archive)
    if actual != expected:
        raise SystemExit(f"source payload hash mismatch: expected={expected} actual={actual}")
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(WORK)

    # Dalamud API development files.
    latest = WORK / "dalamud-latest.zip"
    urllib.request.urlretrieve("https://goatcorp.github.io/dalamud-distrib/latest.zip", latest)
    dev = Path(os.environ["APPDATA"]) / "XIVLauncher" / "addon" / "Hooks" / "dev"
    dev.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(latest) as zf:
        zf.extractall(dev)

    # Regression tests.
    test_outputs: list[str] = []
    tests = sorted((SOURCE / "tests").glob("*.py"))
    for test in tests:
        proc = subprocess.run([sys.executable, str(test)], cwd=SOURCE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        test_outputs.append(f"===== {test.name} =====\n{proc.stdout}")
        if proc.returncode != 0:
            (LOGS / "test.log").write_text("\n".join(test_outputs), encoding="utf-8")
            raise SystemExit(f"test failed: {test.name}")
    (LOGS / "test.log").write_text("\n".join(test_outputs), encoding="utf-8")

    env = {"DOTNET_CLI_UI_LANGUAGE": "en", "DOTNET_NOLOGO": "1"}
    run(["dotnet", "--info"], SOURCE, LOGS / "dotnet-info.log", env)
    project = SOURCE / "CrescentSetupDirector.csproj"
    run(["dotnet", "restore", str(project), "--locked-mode"], SOURCE, LOGS / "restore.log", env)
    run(["dotnet", "build", str(project), "-c", "Release", "--no-restore"], SOURCE, LOGS / "build.log", env)

    dlls = [p for p in SOURCE.rglob("CrescentSetupDirector.dll") if "obj" not in p.parts]
    if not dlls:
        raise SystemExit("built DLL not found")
    dll = min(dlls, key=lambda p: len(p.parts))
    out_dir = dll.parent
    for name in ["CrescentSetupDirector.dll", "CrescentSetupDirector.deps.json", "CrescentSetupDirector.json"]:
        p = out_dir / name
        if not p.exists():
            matches = [x for x in SOURCE.rglob(name) if "obj" not in x.parts]
            if not matches:
                raise SystemExit(f"built companion file missing: {name}")
            p = matches[0]
        shutil.copy2(p, PLUGIN / name)

    shutil.copy2(archive, ARTIFACT / archive.name)
    shutil.copy2(REPO / "source_v0.2.4.sha256", ARTIFACT / "source_v0.2.4.sha256")
    build_text = (LOGS / "build.log").read_text(encoding="utf-8", errors="replace")
    proof = {
        "version": "0.2.4",
        "target": "net10.0-windows / Dalamud API 15",
        "source_sha256": actual,
        "test_count": len(tests),
        "tests_passed": len(tests),
        "build_zero_errors": "0 Error(s)" in build_text,
        "build_zero_warnings": "0 Warning(s)" in build_text,
        "files": {p.name: {"size": p.stat().st_size, "sha256": sha256(p)} for p in sorted(PLUGIN.iterdir())},
    }
    (REPORTS / "BUILD_PROOF.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    if not proof["build_zero_errors"] or not proof["build_zero_warnings"]:
        raise SystemExit("build did not report zero warnings and zero errors")
    print(json.dumps(proof, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
