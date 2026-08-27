from __future__ import annotations
import base64, gzip, hashlib, json, os, shutil, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'csd_v0210_r6_final'
ART = HERE / 'build-artifact'
LOGS = ART / 'LOGS'
PLUGIN = ART / 'PLUGIN_FILES'
REPORTS = ART / 'REPORTS'
BUILD_ID = 'CSD_V0210_API15_NET10_CE_IMMEDIATE_BURST_BLACK_REGIMENT_R6_20260827'
EXPECTED_TEST_COUNT = 68
BASE_RUN_ID = '33038075378'
BASE_ARTIFACT = 'CSD-v0.2.9-verified'

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def run(cmd:list[str], cwd:Path, log:Path|None=None, env:dict[str,str]|None=None)->str:
    merged=os.environ.copy(); merged.update(env or {})
    p=subprocess.run(cmd,cwd=cwd,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=merged)
    if log:
        log.parent.mkdir(parents=True,exist_ok=True); log.write_text(p.stdout,encoding='utf-8',errors='replace')
    print(p.stdout)
    if p.returncode: raise SystemExit(f'command failed {p.returncode}: {cmd}')
    return p.stdout

def main()->None:
    shutil.rmtree(WORK,ignore_errors=True); shutil.rmtree(ART,ignore_errors=True)
    WORK.mkdir(parents=True); LOGS.mkdir(parents=True); PLUGIN.mkdir(parents=True); REPORTS.mkdir(parents=True)

    base=WORK/'base_artifact'
    run(['gh','run','download',BASE_RUN_ID,'-n',BASE_ARTIFACT,'-D',str(base)],ROOT,LOGS/'download-base.log')
    src_zip=base/'Crescent_Setup_Director_v0.2.9_R3_SOURCE_VERIFIED.zip'
    if not src_zip.exists(): raise SystemExit(f'base source zip missing: {src_zip}')
    extracted=WORK/'base_source'
    with zipfile.ZipFile(src_zip) as z: z.extractall(extracted)
    source=extracted/'source'
    if not (source/'SetupEngine.cs').exists(): raise SystemExit('base source extraction invalid')

    patch_gz=WORK/'apply_r6.py.gz'
    patch_gz.write_bytes(base64.b64decode((HERE/'apply_r6.py.gz.b64').read_text(encoding='ascii'),validate=True))
    if sha(patch_gz)!='e5f40b2785562e9f0091f0f83f603a6cfc44148b88775889f6a29439a9c86ac0':
        raise SystemExit('R6 patch payload SHA mismatch')
    patch_py=WORK/'apply_r6.py'
    patch_py.write_bytes(gzip.decompress(patch_gz.read_bytes()))
    run([sys.executable,str(patch_py),str(source)],ROOT,LOGS/'apply-r6.log')

    tests_zip=WORK/'r6_tests.zip'
    tests_zip.write_bytes(base64.b64decode((HERE/'r6_tests.zip.b64').read_text(encoding='ascii'),validate=True))
    if sha(tests_zip)!='36e4043bd7e7a10595208dba88a39e63e6427dee27be0b6ec5c8a3f332026710':
        raise SystemExit('R6 tests payload SHA mismatch')
    with zipfile.ZipFile(tests_zip) as z: z.extractall(source)

    tests=sorted((source/'tests').glob('*.py'))
    if len(tests)!=EXPECTED_TEST_COUNT: raise SystemExit(f'expected {EXPECTED_TEST_COUNT} tests, found {len(tests)}')
    outputs=[]
    tenv={'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
    for test in tests:
        p=subprocess.run([sys.executable,str(test)],cwd=source,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env={**os.environ,**tenv})
        outputs.append(f'===== {test.name} =====\n{p.stdout}')
        if p.returncode:
            (LOGS/'regression-tests.log').write_text('\n'.join(outputs),encoding='utf-8')
            raise SystemExit(f'regression test failed: {test.name}')
    (LOGS/'regression-tests.log').write_text('\n'.join(outputs),encoding='utf-8')

    latest=WORK/'dalamud-latest.zip'
    urllib.request.urlretrieve('https://goatcorp.github.io/dalamud-distrib/latest.zip',latest)
    dev=Path(os.environ['APPDATA'])/'XIVLauncher'/'addon'/'Hooks'/'dev'; dev.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(latest) as z: z.extractall(dev)

    denv={'DOTNET_CLI_UI_LANGUAGE':'en','DOTNET_NOLOGO':'1'}
    project=source/'CrescentSetupDirector.csproj'
    run(['dotnet','--info'],source,LOGS/'dotnet-info.log',denv)
    run(['dotnet','restore',str(project),'--locked-mode'],source,LOGS/'restore.log',denv)
    build_log=run(['dotnet','build',str(project),'-c','Release','--no-restore'],source,LOGS/'build.log',denv)

    outputs=[p for p in source.rglob('CrescentSetupDirector.dll') if 'obj' not in p.parts]
    if not outputs: raise SystemExit('DLL not produced')
    dll=min(outputs,key=lambda p:len(p.parts)); out=dll.parent
    for name in ['CrescentSetupDirector.dll','CrescentSetupDirector.deps.json','CrescentSetupDirector.json']:
        p=out/name
        if not p.exists(): p=next((x for x in source.rglob(name) if 'obj' not in x.parts),None)
        if p is None or not p.exists(): raise SystemExit(f'missing output {name}')
        shutil.copy2(p,PLUGIN/name)

    manifest=json.loads((PLUGIN/'CrescentSetupDirector.json').read_text(encoding='utf-8-sig'))
    if manifest.get('AssemblyVersion')!='0.2.10.0' or manifest.get('DalamudApiLevel')!=15: raise SystemExit(f'bad manifest: {manifest}')
    raw=(PLUGIN/'CrescentSetupDirector.dll').read_bytes()
    if BUILD_ID.encode() not in raw and BUILD_ID.encode('utf-16le') not in raw: raise SystemExit('Build ID missing from DLL')

    source_zip=ART/'Crescent_Setup_Director_v0.2.10_R6_SOURCE_VERIFIED.zip'
    with zipfile.ZipFile(source_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=False) as z:
        for p in sorted(source.rglob('*')):
            rel=p.relative_to(source)
            if p.is_file() and not any(x in {'bin','obj','__pycache__'} for x in rel.parts): z.write(p,Path('source')/rel)

    proof={'version':'0.2.10','assembly_version':manifest.get('AssemblyVersion'),'build_id':BUILD_ID,'target':'net10.0-windows / Dalamud API 15','tests_passed':len(tests),'test_count':len(tests),'build_zero_warnings':'0 Warning(s)' in build_log,'build_zero_errors':'0 Error(s)' in build_log,'base_run_id':BASE_RUN_ID,'base_source_sha256':sha(src_zip),'source_zip_sha256':sha(source_zip),'files':{p.name:{'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(PLUGIN.iterdir())}}
    (REPORTS/'BUILD_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False,indent=2))
    if not proof['build_zero_warnings'] or not proof['build_zero_errors']: raise SystemExit('build warnings/errors detected')

if __name__=='__main__': main()
