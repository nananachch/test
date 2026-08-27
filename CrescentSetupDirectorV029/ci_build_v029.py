from __future__ import annotations
import base64, hashlib, json, os, shutil, subprocess, sys, tarfile, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ.get('RUNNER_TEMP', HERE / '_tmp')) / 'csd_v029_r3'
SOURCE = WORK / 'source'
ART = HERE / 'build-artifact'
LOGS = ART / 'LOGS'
PLUGIN = ART / 'PLUGIN_FILES'
REPORTS = ART / 'REPORTS'
VERSION = '0.2.9'
BUILD_ID = 'CSD_V029_API15_NET10_CE_POT_MANUAL_BASE_R3_20260827'
SOURCE_ARCHIVE = WORK / 'source_v0.2.9.r2.tar.bz2'
SOURCE_ARCHIVE_SHA256 = '2cf4c001eccafacfddf459c15fef27170572a3bee15519da8f76d9d961c56010'
EXPECTED_TEST_COUNT = 58

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

def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'R3 source patch marker missing: {path.name}: {old[:80]}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')

def apply_r3_source_patch() -> None:
    setup_path = SOURCE / 'SetupEngine.cs'
    setup_text = setup_path.read_text(encoding='utf-8')
    for marker in [
        '    private bool globalMoveRequested;\n',
        '    private DateTime globalTravelStartedUtc;\n',
        '        globalMoveRequested = false;\n',
        '        globalTravelStartedUtc = default;\n',
    ]:
        setup_text = setup_text.replace(marker, '')
    if 'globalMoveRequested' in setup_text or 'globalTravelStartedUtc' in setup_text:
        raise SystemExit('obsolete automatic global-buff travel state remains')
    setup_path.write_text(setup_text, encoding='utf-8', newline='\n')

    replace_required(SOURCE/'BuildIdentity.cs',
        'CSD_V029_API15_NET10_CE_POT_MANUAL_BASE_R2_20260827', BUILD_ID)
    replace_required(SOURCE/'CrescentSetupDirector.csproj',
        '0.2.9+CSD_V029_API15_NET10_CE_DUAL_ROUTE_MANUAL_RETURN_20260827_R1',
        f'0.2.9+{BUILD_ID}')
    replace_required(SOURCE/'CrescentSetupDirector.csproj',
        'クレセントアイルの通常FATE、CE、マジックポットを排他的な状態機械で管理します。CEは40秒前にRSR/BMRを完全停止し、風水士ベル後は吟遊詩人で待機します。通常型は暗転明けに歌→警戒→設定最終サポート、短期決戦型は暗転1秒前に歌、暗転明けに警戒→ねらう→侍で戦闘開始待ちを実行します。長時間バフは残り時間だけでは帰還せず、手動デジョン後の拠点付近でのみ降車→更新→元サポート復元を行います。ポットは境界手前から準備し、予言士など最終サポートを戦闘前に確定します。初期状態はDRY RUNです。',
        'クレセントアイルの通常FATE、CE、マジックポットを排他的な状態機械で管理します。CEは40秒前にRSR/BMRを完全停止し、風水士で停止します。通常型は暗転明けに歌→警戒→設定最終サポート、短期決戦型は暗転1秒前に歌、暗転明けに警戒→ねらう→侍で戦闘開始待ちを実行します。長時間バフは自動帰還せず、手動で拠点クリスタル30m以内へ戻った安全状態でだけ残り時間を判定して更新します。ポットはFATE範囲内で準備し、南征編・北1PはRSRをOFFのまま予言士で手動まとめを待ち、2Pから侍へ変更してRSR/BMRをONにします。初期状態はDRY RUNです。')
    replace_required(SOURCE/'Windows/ConfigWindow.cs',
        'Checkbox("手動デジョン後、残り時間が閾値未満なら更新"',
        'Checkbox("手動で拠点へ戻った後、残り時間が閾値未満なら更新"')
    replace_required(SOURCE/'tests/20_source_package_safety.py',
        "    assert 'powershell.exe' not in text and 'pwsh.exe' not in text and 'start-process' not in text\nprint('PASS 20 no SDK payload and no PowerShell runtime dependency')",
        "    blocked = ['power'+'shell.exe', 'pw'+'sh.exe', 'start-'+'process']\n    assert all(token not in text for token in blocked)\nprint('PASS 20 no SDK payload and no alternate shell runtime dependency')")
    replace_required(SOURCE/'tests/34_build_identity_and_loaded_dll_proof.py',
        "assert 'CSD_V029_API15_NET10_CE_POT_MANUAL_BASE_R2_20260827' in b and '0.2.9' in proj",
        f"assert '{BUILD_ID}' in b and '0.2.9' in proj")
    replace_required(SOURCE/'tests/34_build_identity_and_loaded_dll_proof.py',
        'PASS 34 v0.2.9 R2 provenance', 'PASS 34 v0.2.9 R3 provenance')
    replace_required(SOURCE/'CHANGELOG.md', '## v0.2.9 R2', '## v0.2.9 R3')
    replace_required(SOURCE/'CHANGELOG.md',
        '- Long-duration buff time is evaluated only after manual arrival within 30m of the base crystal; all automatic walking is disabled.',
        '- Long-duration buff time is evaluated only after manual arrival within 30m of the base crystal; CSD performs neither Return nor walking.')
    replace_required(SOURCE/'CHANGELOG.md',
        '- 長時間バフは残り9分台になっただけではデジョンも徒歩帰還も開始しない。手動デジョン後に拠点クリスタル180m以内へ戻った場合だけ、降車→短距離移動→降車再確認→更新→元サポート復元を行う。',
        '- 長時間バフは残り9分台になっただけではデジョンも徒歩帰還も開始しない。ユーザーが手動で拠点へ戻り、クリスタル30m以内かつ安全状態になった後だけ残り時間を判定し、必要なバフを更新して元サポートへ復元する。')
    replace_required(SOURCE/'CHANGELOG.md',
        '- ポットは固有FATEの境界手前から事前準備を開始し、南征編・北1Pではサポ予言士へ変更完了後にFATE範囲内待ちへ入る。フェーズ境界ではRSR/BMRを先に停止し、非戦闘状態を確認してから次サポート変更へ進む。',
        '- ポットは固有FATEの範囲内へ入ってから準備を開始する。南征編・北1PではRSRを完全OFFにし、サポ予言士で手動まとめと実戦闘終了を待つ。2Pはサポ侍へ変更後にRSR/BMRをONにする。')

    for forbidden in ['境界手前', '180m', '手動デジョン後', 'CSD_V029_API15_NET10_CE_POT_MANUAL_BASE_R2_20260827', 'CE_DUAL_ROUTE_MANUAL_RETURN']:
        for path in SOURCE.rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.cs','.csproj','.py','.md','.json','.txt'}:
                if forbidden in path.read_text(encoding='utf-8', errors='ignore'):
                    raise SystemExit(f'stale R2/R1 text remains: {forbidden}: {path}')

def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True); shutil.rmtree(ART, ignore_errors=True)
    SOURCE.mkdir(parents=True); LOGS.mkdir(parents=True); PLUGIN.mkdir(parents=True); REPORTS.mkdir(parents=True)
    chunks = sorted((HERE / 'chunks').glob('source_v0.2.9.r2.tbz2.b64.*'))
    if not chunks: raise SystemExit('R2 transport archive chunks missing')
    SOURCE_ARCHIVE.write_bytes(base64.b64decode(''.join(x.read_text(encoding='ascii').strip() for x in chunks)))
    if sha(SOURCE_ARCHIVE) != SOURCE_ARCHIVE_SHA256: raise SystemExit('R2 transport archive SHA-256 mismatch')
    with tarfile.open(SOURCE_ARCHIVE, 'r:bz2') as tf: tf.extractall(SOURCE, filter='data')
    apply_r3_source_patch()

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
    if manifest.get('AssemblyVersion')!='0.2.9.0' or manifest.get('DalamudApiLevel')!=15:
        raise SystemExit(f'bad manifest: {manifest}')
    if 'FATE範囲内で準備' not in manifest.get('Description','') or '境界手前' in manifest.get('Description',''):
        raise SystemExit(f'stale plugin description: {manifest.get("Description")}')
    dll_bytes=(PLUGIN/'CrescentSetupDirector.dll').read_bytes()
    if BUILD_ID.encode('utf-8') not in dll_bytes and BUILD_ID.encode('utf-16le') not in dll_bytes:
        raise SystemExit('new R3 Build ID was not found in DLL bytes')

    source_zip=ART/'Crescent_Setup_Director_v0.2.9_R3_SOURCE_VERIFIED.zip'
    with zipfile.ZipFile(source_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=False) as zf:
        for path in sorted(SOURCE.rglob('*')):
            rel=path.relative_to(SOURCE)
            if path.is_file() and not any(part in {'bin','obj','__pycache__'} for part in rel.parts):
                zf.write(path,Path('source')/rel)

    proof={
        'version':VERSION,'assembly_version':manifest.get('AssemblyVersion'),'build_id':BUILD_ID,
        'target':'net10.0-windows / Dalamud API 15','tests_passed':len(tests),'test_count':len(tests),
        'build_zero_warnings':'0 Warning(s)' in build_log,'build_zero_errors':'0 Error(s)' in build_log,
        'transport_source_archive_sha256':SOURCE_ARCHIVE_SHA256,'source_zip_sha256':sha(source_zip),
        'files':{p.name:{'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(PLUGIN.iterdir())},
    }
    (REPORTS/'BUILD_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False,indent=2))
    if not proof['build_zero_warnings'] or not proof['build_zero_errors']:
        raise SystemExit('build had warnings or errors')

if __name__=='__main__': main()
