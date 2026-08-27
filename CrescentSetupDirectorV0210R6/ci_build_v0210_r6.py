from __future__ import annotations
import base64, hashlib, json, os, shutil, subprocess, sys, tarfile, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ.get('RUNNER_TEMP', HERE / '_tmp')) / 'csd_v0210_r6'
SOURCE = WORK / 'source'
ART = HERE / 'build-artifact'
LOGS = ART / 'LOGS'
PLUGIN = ART / 'PLUGIN_FILES'
REPORTS = ART / 'REPORTS'
VERSION = '0.2.10'
ASSEMBLY_VERSION = '0.2.10.0'
BUILD_ID = 'CSD_V0210_API15_NET10_CE_IMMEDIATE_BURST_BLACK_REGIMENT_R6_20260827'
SOURCE_ARCHIVE = WORK / 'source_v0.2.10.r6.tar.bz2'
SOURCE_ARCHIVE_SHA256 = '14fbc6f25545d24d0f455ee97c761a1df6e1f412d5ea19d3a8e5db3a725f4b3b'
EXPECTED_TEST_COUNT = 65

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def run(cmd: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> str:
    merged = os.environ.copy(); merged.update(env or {})
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=merged)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(proc.stdout, encoding='utf-8', errors='replace')
    print(proc.stdout)
    if proc.returncode:
        raise SystemExit(f'command failed {proc.returncode}: {cmd}')
    return proc.stdout

def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True); shutil.rmtree(ART, ignore_errors=True)
    SOURCE.mkdir(parents=True); LOGS.mkdir(parents=True); PLUGIN.mkdir(parents=True); REPORTS.mkdir(parents=True)
    chunks = sorted((HERE / 'chunks2').glob('source_v0.2.10.r6.tbz2.b64.*'))
    if not chunks: raise SystemExit('R6 source archive chunks missing')
    SOURCE_ARCHIVE.write_bytes(base64.b64decode(''.join(x.read_text(encoding='ascii').strip() for x in chunks)))
    if sha(SOURCE_ARCHIVE) != SOURCE_ARCHIVE_SHA256: raise SystemExit('R6 source archive SHA-256 mismatch')
    with tarfile.open(SOURCE_ARCHIVE, 'r:bz2') as tf: tf.extractall(SOURCE, filter='data')

    setup_text=(SOURCE/'SetupEngine.cs').read_text(encoding='utf-8')
    required = [
        'FailOpenCriticalEncounter', 'FailOpenMagicPot', '[POT-FAIL-OPEN]',
        'RunCeBurstPriority', 'RunBlackRegimentOracle', BUILD_ID,
    ]
    for item in required:
        if item not in setup_text and item != BUILD_ID:
            raise SystemExit(f'missing R6 source marker: {item}')
    if BUILD_ID not in (SOURCE/'BuildIdentity.cs').read_text(encoding='utf-8'):
        raise SystemExit('R6 Build ID missing from BuildIdentity.cs')

    tests = sorted((SOURCE / 'tests').glob('*.py'))
    outputs=[]
    tenv={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
    for test in tests:
        proc=subprocess.run([sys.executable,str(test)],cwd=SOURCE,text=True,encoding='utf-8',errors='replace',env=tenv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        outputs.append(f'===== {test.name} =====\n{proc.stdout}')
        if proc.returncode:
            (LOGS/'regression-tests.log').write_text('\n'.join(outputs),encoding='utf-8')
            raise SystemExit(f'regression test failed: {test.name}')
    (LOGS/'regression-tests.log').write_text('\n'.join(outputs),encoding='utf-8')
    if len(tests) != EXPECTED_TEST_COUNT: raise SystemExit(f'expected {EXPECTED_TEST_COUNT} tests, found {len(tests)}')

    latest=WORK/'dalamud-latest.zip'
    urllib.request.urlretrieve('https://goatcorp.github.io/dalamud-distrib/latest.zip',latest)
    dev=Path(os.environ['APPDATA'])/'XIVLauncher'/'addon'/'Hooks'/'dev'; dev.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(latest) as zf: zf.extractall(dev)

    env={'DOTNET_CLI_UI_LANGUAGE':'en','DOTNET_NOLOGO':'1'}
    project=SOURCE/'CrescentSetupDirector.csproj'
    run(['dotnet','--info'],SOURCE,LOGS/'dotnet-info.log',env)
    run(['dotnet','restore',str(project),'--locked-mode'],SOURCE,LOGS/'restore.log',env)
    build_log=run(['dotnet','build',str(project),'-c','Release','--no-restore'],SOURCE,LOGS/'build.log',env)

    candidates=[p for p in SOURCE.rglob('CrescentSetupDirector.dll') if 'obj' not in p.parts]
    if not candidates: raise SystemExit('CrescentSetupDirector.dll was not produced')
    dll=min(candidates,key=lambda p:len(p.parts)); output=dll.parent
    for name in ['CrescentSetupDirector.dll','CrescentSetupDirector.deps.json','CrescentSetupDirector.json']:
        path=output/name
        if not path.exists(): path=next((p for p in SOURCE.rglob(name) if 'obj' not in p.parts),None)
        if path is None or not path.exists(): raise SystemExit(f'missing build output: {name}')
        shutil.copy2(path,PLUGIN/name)

    manifest=json.loads((PLUGIN/'CrescentSetupDirector.json').read_text(encoding='utf-8-sig'))
    if manifest.get('AssemblyVersion')!=ASSEMBLY_VERSION or manifest.get('DalamudApiLevel')!=15:
        raise SystemExit(f'bad manifest: {manifest}')
    dll_bytes=(PLUGIN/'CrescentSetupDirector.dll').read_bytes()
    if BUILD_ID.encode('utf-8') not in dll_bytes and BUILD_ID.encode('utf-16le') not in dll_bytes:
        raise SystemExit('R6 Build ID was not found in DLL bytes')

    source_zip=ART/'CSD_v0.2.10_R6_SOURCE_VERIFIED.zip'
    with zipfile.ZipFile(source_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=False) as zf:
        for path in sorted(SOURCE.rglob('*')):
            rel=path.relative_to(SOURCE)
            if path.is_file() and not any(part in {'bin','obj','__pycache__'} for part in rel.parts):
                zf.write(path,Path('source')/rel)

    proof={
        'version':VERSION,'assembly_version':manifest.get('AssemblyVersion'),'build_id':BUILD_ID,
        'target':'net10.0-windows / Dalamud API 15','tests_passed':len(tests),'test_count':len(tests),
        'build_zero_warnings':'0 Warning(s)' in build_log,'build_zero_errors':'0 Error(s)' in build_log,
        'source_archive_sha256':SOURCE_ARCHIVE_SHA256,'source_zip_sha256':sha(source_zip),
        'files':{p.name:{'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(PLUGIN.iterdir())},
    }
    (REPORTS/'BUILD_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False,indent=2))
    if not proof['build_zero_warnings'] or not proof['build_zero_errors']:
        raise SystemExit('build had warnings or errors')

if __name__=='__main__': main()
