from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
import urllib.request
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
WORK = pathlib.Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "csd_v0211_r7_final"
ART = HERE / "build-artifact"
LOGS = ART / "LOGS"
PLUGIN = ART / "PLUGIN_FILES"
REPORTS = ART / "REPORTS"

BASE_RUN_ID = "33097493698"
BASE_ARTIFACT = "CSD-v0.2.10-R6-verified"
BASE_SOURCE_NAME = "Crescent_Setup_Director_v0.2.10_R6_SOURCE_VERIFIED.zip"
BASE_TAR_SHA256 = "536a06b6a7e02288bda7b2f752c7b0cc17dd1332e3ce7a935b848f5cbe784922"
PATCH_SHA256 = "e7167eeeaf6b1599069eeadf3176f3017909dc0e87e3077e305a2db9ea1fd30e"
R7_TAR_SHA256 = "806fd950e8225b2b4dbe24fd24f51d315dd843acbb90c049bc3b02d4a3bb849b"
BUILD_ID = "CSD_V0211_API15_NET10_ALL_REPORTED_BUGFIX_R7_20260828"
EXPECTED_TESTS = 78
ZSTD_URL = "https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-v1.5.7-win64.zip"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], cwd: pathlib.Path, log_path: pathlib.Path, env: dict[str, str] | None = None) -> str:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    process = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(process.stdout, encoding="utf-8", errors="replace")
    print(process.stdout)
    if process.returncode:
        raise SystemExit(f"command failed ({process.returncode}): {command}")
    return process.stdout


def source_files(source: pathlib.Path) -> list[pathlib.Path]:
    excluded = {"bin", "obj", "__pycache__", ".git"}
    return sorted(path for path in source.rglob("*") if path.is_file() and not any(part in excluded for part in path.relative_to(source).parts))


def write_deterministic_tar(source: pathlib.Path, destination: pathlib.Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in source_files(source):
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(source).as_posix())
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o666
            archive.addfile(info, io.BytesIO(data))


def find_source_zip(root: pathlib.Path) -> pathlib.Path:
    exact = root / BASE_SOURCE_NAME
    if exact.exists():
        return exact
    candidates = sorted(root.rglob("*R6*SOURCE*VERIFIED*.zip"))
    if len(candidates) != 1:
        raise SystemExit(f"could not uniquely find R6 source ZIP: {candidates}")
    return candidates[0]


def get_zstd(work: pathlib.Path) -> pathlib.Path:
    existing = shutil.which("zstd") or shutil.which("zstd.exe")
    if existing:
        return pathlib.Path(existing)
    archive = work / "zstd.zip"
    install = work / "zstd"
    urllib.request.urlretrieve(ZSTD_URL, archive)
    with zipfile.ZipFile(archive) as zipped:
        bad = zipped.testzip()
        if bad:
            raise SystemExit(f"bad zstd ZIP entry: {bad}")
        zipped.extractall(install)
    executables = sorted(install.rglob("zstd.exe"))
    if not executables:
        raise SystemExit("zstd.exe not found in downloaded release")
    return executables[0]


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(ART, ignore_errors=True)
    WORK.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    PLUGIN.mkdir(parents=True)
    REPORTS.mkdir(parents=True)

    base_artifact = WORK / "base-artifact"
    run(["gh", "run", "download", BASE_RUN_ID, "-n", BASE_ARTIFACT, "-D", str(base_artifact)], REPO_ROOT, LOGS / "download-base.log")
    base_source_zip = find_source_zip(base_artifact)
    base_extract = WORK / "base-extract"
    with zipfile.ZipFile(base_source_zip) as zipped:
        bad = zipped.testzip()
        if bad:
            raise SystemExit(f"bad base source ZIP entry: {bad}")
        zipped.extractall(base_extract)
    base_source = base_extract / "source"
    if not (base_source / "SetupEngine.cs").exists():
        raise SystemExit("base source extraction is invalid")

    base_tar = WORK / "r6.tar"
    write_deterministic_tar(base_source, base_tar)
    if sha256(base_tar) != BASE_TAR_SHA256:
        raise SystemExit(f"base tar SHA mismatch: {sha256(base_tar)}")

    patch_parts = sorted((HERE / "zpatch").glob("patch.b64.*"))
    if len(patch_parts) != 4:
        raise SystemExit(f"expected 4 patch chunks, found {len(patch_parts)}")
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in patch_parts)
    patch = WORK / "r6_to_r7.zstpatch"
    patch.write_bytes(base64.b64decode(encoded, validate=True))
    if sha256(patch) != PATCH_SHA256:
        raise SystemExit(f"patch SHA mismatch: {sha256(patch)}")

    r7_tar = WORK / "r7.tar"
    zstd = get_zstd(WORK)
    run([str(zstd), "-d", f"--patch-from={base_tar}", str(patch), "-o", str(r7_tar)], WORK, LOGS / "zstd-patch.log")
    if sha256(r7_tar) != R7_TAR_SHA256:
        raise SystemExit(f"R7 tar SHA mismatch: {sha256(r7_tar)}")

    source = WORK / "source"
    source.mkdir()
    with tarfile.open(r7_tar, "r") as archive:
        archive.extractall(source, filter="data")
    if BUILD_ID not in (source / "BuildIdentity.cs").read_text(encoding="utf-8"):
        raise SystemExit("R7 Build ID missing from source")

    tests = sorted((source / "tests").glob("*.py"))
    if len(tests) != EXPECTED_TESTS:
        raise SystemExit(f"expected {EXPECTED_TESTS} tests, found {len(tests)}")
    test_log: list[str] = []
    failures: list[str] = []
    for test in tests:
        test_log.append(f"===== {test.name} =====")
        try:
            runpy.run_path(str(test), run_name="__main__")
            test_log.append("PASS")
        except BaseException:
            detail = traceback.format_exc()
            failures.append(f"{test.name}\n{detail}")
            test_log.append(detail)
    (LOGS / "regression-tests.log").write_text("\n".join(test_log), encoding="utf-8")
    if failures:
        raise SystemExit("\n".join(failures))

    dalamud_zip = WORK / "dalamud-latest.zip"
    urllib.request.urlretrieve("https://goatcorp.github.io/dalamud-distrib/latest.zip", dalamud_zip)
    dalamud_dev = pathlib.Path(os.environ["APPDATA"]) / "XIVLauncher" / "addon" / "Hooks" / "dev"
    dalamud_dev.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dalamud_zip) as zipped:
        bad = zipped.testzip()
        if bad:
            raise SystemExit(f"bad Dalamud ZIP entry: {bad}")
        zipped.extractall(dalamud_dev)

    dotnet_env = {"DOTNET_CLI_UI_LANGUAGE": "en", "DOTNET_NOLOGO": "1"}
    project = source / "CrescentSetupDirector.csproj"
    run(["dotnet", "--info"], source, LOGS / "dotnet-info.log", dotnet_env)
    run(["dotnet", "restore", str(project), "--locked-mode"], source, LOGS / "restore.log", dotnet_env)
    build_log = run(["dotnet", "build", str(project), "-c", "Release", "--no-restore"], source, LOGS / "build.log", dotnet_env)

    dll_candidates = [path for path in source.rglob("CrescentSetupDirector.dll") if "obj" not in path.parts]
    if not dll_candidates:
        raise SystemExit("CrescentSetupDirector.dll was not produced")
    output = min(dll_candidates, key=lambda path: len(path.parts)).parent
    for name in ("CrescentSetupDirector.dll", "CrescentSetupDirector.deps.json", "CrescentSetupDirector.json"):
        path = output / name
        if not path.exists():
            path = next((candidate for candidate in source.rglob(name) if "obj" not in candidate.parts), None)
        if path is None or not path.exists():
            raise SystemExit(f"missing build output: {name}")
        shutil.copy2(path, PLUGIN / name)

    manifest = json.loads((PLUGIN / "CrescentSetupDirector.json").read_text(encoding="utf-8-sig"))
    if manifest.get("AssemblyVersion") != "0.2.11.0":
        raise SystemExit(f"bad AssemblyVersion: {manifest.get('AssemblyVersion')}")
    if manifest.get("DalamudApiLevel") != 15:
        raise SystemExit(f"bad DalamudApiLevel: {manifest.get('DalamudApiLevel')}")
    dll_data = (PLUGIN / "CrescentSetupDirector.dll").read_bytes()
    if BUILD_ID.encode("utf-8") not in dll_data and BUILD_ID.encode("utf-16le") not in dll_data:
        raise SystemExit("Build ID missing from DLL bytes")

    source_zip = ART / "Crescent_Setup_Director_v0.2.11_R7_SOURCE_VERIFIED.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False) as zipped:
        for path in source_files(source):
            zipped.write(path, pathlib.Path("source") / path.relative_to(source))
    with zipfile.ZipFile(source_zip) as zipped:
        bad = zipped.testzip()
        if bad:
            raise SystemExit(f"bad verified source ZIP entry: {bad}")

    proof = {
        "version": "0.2.11",
        "assembly_version": manifest.get("AssemblyVersion"),
        "build_id": BUILD_ID,
        "target": "net10.0-windows / Dalamud API 15",
        "tests_passed": len(tests),
        "test_count": len(tests),
        "build_zero_warnings": "0 Warning(s)" in build_log,
        "build_zero_errors": "0 Error(s)" in build_log,
        "base_run_id": BASE_RUN_ID,
        "base_source_zip_sha256": sha256(base_source_zip),
        "base_tar_sha256": sha256(base_tar),
        "patch_sha256": sha256(patch),
        "r7_tar_sha256": sha256(r7_tar),
        "source_zip_sha256": sha256(source_zip),
        "files": {path.name: {"size": path.stat().st_size, "sha256": sha256(path)} for path in sorted(PLUGIN.iterdir())},
    }
    (REPORTS / "BUILD_PROOF.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    if not proof["build_zero_warnings"] or not proof["build_zero_errors"]:
        raise SystemExit("build produced warnings or errors")


if __name__ == "__main__":
    main()
