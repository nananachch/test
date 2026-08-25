from __future__ import annotations
import base64, hashlib, json, os, shutil, subprocess, sys, tarfile, urllib.request, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
V024=ROOT/'CrescentSetupDirectorV024Final'
WORK=Path(os.environ.get('RUNNER_TEMP',HERE/'_tmp'))/'csd_v025'
SOURCE=WORK/'source'
ART=HERE/'build-artifact'; LOGS=ART/'LOGS'; PLUGIN=ART/'PLUGIN_FILES'; REPORTS=ART/'REPORTS'
VERSION='0.2.5'; BUILD_ID='CSD_V025_API15_NET10_LIVE_PROVENANCE_20260825_R1'

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def run(cmd,cwd,log,env=None):
 e=os.environ.copy(); e.update(env or {})
 p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=e)
 log.parent.mkdir(parents=True,exist_ok=True); log.write_text(p.stdout,encoding='utf-8',errors='replace'); print(p.stdout)
 if p.returncode: raise SystemExit(f'command failed {p.returncode}: {cmd}')

def patch_source():
 (SOURCE/'BuildIdentity.cs').write_text(r'''using System.Security.Cryptography;
namespace CrescentSetupDirector;
public static class BuildIdentity
{
    public const string Version = "0.2.5";
    public const string AssemblyVersion = "0.2.5.0";
    public const string BuildId = "CSD_V025_API15_NET10_LIVE_PROVENANCE_20260825_R1";
    public static string LoadedAssemblyPath { get; } = GetLoadedAssemblyPath();
    public static string LoadedAssemblySha256 { get; } = ComputeSha256(LoadedAssemblyPath);
    public static string ExpectedFixedAssemblyPath { get; } = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Documents", "Codex", "Projects", "CrescentSetupDirector", "Latest_Source", "_BUNDLE", "INSTALL", "Expanded_Plugin", "CrescentSetupDirector.dll");
    public static bool IsLoadedFromExpectedFixedPath { get; } = PathsEqual(LoadedAssemblyPath, ExpectedFixedAssemblyPath);
    private static string GetLoadedAssemblyPath(){try{var x=typeof(BuildIdentity).Assembly.Location;return string.IsNullOrWhiteSpace(x)?"<assembly-location-unavailable>":Path.GetFullPath(x);}catch(Exception ex){return $"<assembly-location-error:{ex.GetType().Name}>";}}
    private static string ComputeSha256(string path){try{if(string.IsNullOrWhiteSpace(path)||path.StartsWith('<')||!File.Exists(path))return "UNAVAILABLE";using var s=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete,1024*1024,FileOptions.SequentialScan);return Convert.ToHexString(SHA256.HashData(s)).ToLowerInvariant();}catch(Exception ex){return $"ERROR-{ex.GetType().Name}";}}
    private static bool PathsEqual(string a,string b){try{return string.Equals(Path.GetFullPath(a).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),Path.GetFullPath(b).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),StringComparison.OrdinalIgnoreCase);}catch{return false;}}
}
''',encoding='utf-8')
 p=SOURCE/'Plugin.cs'; s=p.read_text(encoding='utf-8')
 s=s.replace('Diagnostics.Write($"Crescent Setup Director 0.2.4 loaded. DRY_RUN={Configuration.DryRun}");','''Diagnostics.Write($"[BUILD] version={BuildIdentity.Version} assemblyVersion={BuildIdentity.AssemblyVersion} buildId={BuildIdentity.BuildId} dllSha256={BuildIdentity.LoadedAssemblySha256} dllPath={BuildIdentity.LoadedAssemblyPath} expectedPath={BuildIdentity.ExpectedFixedAssemblyPath} pathMatch={BuildIdentity.IsLoadedFromExpectedFixedPath}");
        Diagnostics.Write($"Crescent Setup Director {BuildIdentity.Version} loaded. DRY_RUN={Configuration.DryRun}");
        ChatGui.Print($"[CSD] v{BuildIdentity.Version} / {BuildIdentity.BuildId} を読み込みました。DLL SHA-256: {BuildIdentity.LoadedAssemblySha256}");
        if (!BuildIdentity.IsLoadedFromExpectedFixedPath) { ChatGui.PrintError("[CSD] 読み込んだDLLが固定先と一致しません。/csd info で実パスを確認してください。"); Diagnostics.Write($"[BUILD-PATH-MISMATCH] actual={BuildIdentity.LoadedAssemblyPath} expected={BuildIdentity.ExpectedFixedAssemblyPath}"); }''')
 s=s.replace('HelpMessage = "/csd: 設定画面, stop: 緊急停止, dryrun on|off, learn reset（FATE/CE/ポットは自動）",','HelpMessage = "/csd: 設定画面, info: 版/Build ID/読込DLL確認, stop: 緊急停止, dryrun on|off, learn reset（FATE/CE/ポットは自動）",')
 s=s.replace('''        {
            case "stop": Engine.EmergencyStop(); break;''','''        {
            case "info":
                ChatGui.Print($"[CSD] v{BuildIdentity.Version} / Assembly {BuildIdentity.AssemblyVersion}"); ChatGui.Print($"[CSD] Build ID: {BuildIdentity.BuildId}"); ChatGui.Print($"[CSD] DLL SHA-256: {BuildIdentity.LoadedAssemblySha256}"); ChatGui.Print($"[CSD] 読込DLL: {BuildIdentity.LoadedAssemblyPath}"); ChatGui.Print($"[CSD] 固定先一致: {(BuildIdentity.IsLoadedFromExpectedFixedPath ? "YES" : "NO")}"); if (!BuildIdentity.IsLoadedFromExpectedFixedPath) ChatGui.PrintError($"[CSD] 期待する固定先: {BuildIdentity.ExpectedFixedAssemblyPath}"); break;
            case "stop": Engine.EmergencyStop(); break;''')
 p.write_text(s,encoding='utf-8')
 p=SOURCE/'Windows'/'ConfigWindow.cs'; s=p.read_text(encoding='utf-8')
 s=s.replace('''        ImGui.Separator();
        ImGui.TextUnformatted($"状態: {plugin.Engine.StateSummary}");''','''        ImGui.Separator();
        ImGui.TextUnformatted($"Build: v{BuildIdentity.Version} / {BuildIdentity.BuildId}"); ImGui.TextWrapped($"読込DLL: {BuildIdentity.LoadedAssemblyPath}"); ImGui.TextWrapped($"DLL SHA-256: {BuildIdentity.LoadedAssemblySha256}"); ImGui.TextUnformatted($"固定先一致: {(BuildIdentity.IsLoadedFromExpectedFixedPath ? "YES" : "NO")}"); if (!BuildIdentity.IsLoadedFromExpectedFixedPath) ImGui.TextWrapped($"期待する固定先: {BuildIdentity.ExpectedFixedAssemblyPath}");
        ImGui.TextUnformatted($"状態: {plugin.Engine.StateSummary}");''')
 s=s.replace('{ config.NormalFateRoute = NormalFateRouteMode.DragoonSurvival; changed = true; }','{ config.NormalFateRoute = NormalFateRouteMode.DragoonSurvival; changed = true; }\n        ImGui.TextWrapped($"現在の通常FATEルート: {(config.NormalFateRoute == NormalFateRouteMode.DragoonSurvival ? "サポ竜騎士固定" : "ぜになげ可=サポ侍／リキャ中=サポ黒魔道士")}");',1)
 s=s.replace('changed |= SupportSelector("ce", config.CeSupportJob, value => config.CeSupportJob = value, includeSpecial: false);','changed |= SupportSelector("ce", config.CeSupportJob, value => config.CeSupportJob = value, includeSpecial: false);\n        ImGui.TextWrapped($"現在のCE設定サポート: {(config.CeSupportJob == SupportJobChoice.Dragoon ? "竜騎士" : "侍")}");')
 p.write_text(s,encoding='utf-8')
 p=SOURCE/'CrescentSetupDirector.csproj'; s=p.read_text(encoding='utf-8').replace('<Version>0.2.4.0</Version>','<Version>0.2.5.0</Version>\n    <AssemblyVersion>0.2.5.0</AssemblyVersion>\n    <FileVersion>0.2.5.0</FileVersion>\n    <InformationalVersion>0.2.5+CSD_V025_API15_NET10_LIVE_PROVENANCE_20260825_R1</InformationalVersion>')
 p.write_text(s,encoding='utf-8')
 (SOURCE/'tests'/'34_build_identity_and_loaded_dll_proof.py').write_text("from pathlib import Path\nr=Path(__file__).resolve().parents[1]\nb=(r/'BuildIdentity.cs').read_text(encoding='utf-8');p=(r/'Plugin.cs').read_text(encoding='utf-8');w=(r/'Windows'/'ConfigWindow.cs').read_text(encoding='utf-8');c=(r/'CrescentSetupDirector.csproj').read_text(encoding='utf-8')\nassert 'CSD_V025_API15_NET10_LIVE_PROVENANCE_20260825_R1' in b and 'LoadedAssemblySha256' in b and 'IsLoadedFromExpectedFixedPath' in b\nassert '[BUILD]' in p and '[BUILD-PATH-MISMATCH]' in p and 'case \\\"info\\\"' in p\nassert '固定先一致' in w and '現在の通常FATEルート' in w and '現在のCE設定サポート' in w\nassert '<Version>0.2.5.0</Version>' in c\nprint('PASS 34 loaded DLL provenance and fixed-path warning')\n",encoding='utf-8')

def main():
 shutil.rmtree(WORK,ignore_errors=True); shutil.rmtree(ART,ignore_errors=True); WORK.mkdir(parents=True); LOGS.mkdir(parents=True); PLUGIN.mkdir(parents=True); REPORTS.mkdir(parents=True)
 chunks=sorted((V024/'chunks').glob('source_v024_final.b64.*')); arc=WORK/'source_v0.2.4.tar.gz'; arc.write_bytes(base64.b64decode(''.join(x.read_text().strip() for x in chunks)))
 exp=(V024/'source_v0.2.4.sha256').read_text().split()[0]
 if sha(arc)!=exp: raise SystemExit('v0.2.4 source hash mismatch')
 with tarfile.open(arc,'r:gz') as tf: tf.extractall(WORK)
 se=SOURCE/'SetupEngine.cs'; se.write_text(se.read_text(encoding='utf-8').replace('    private DateTime pendingBellAcceptedUtc;\n',''),encoding='utf-8')
 patch_source()
 latest=WORK/'dalamud.zip'; urllib.request.urlretrieve('https://goatcorp.github.io/dalamud-distrib/latest.zip',latest); dev=Path(os.environ['APPDATA'])/'XIVLauncher'/'addon'/'Hooks'/'dev'; dev.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(latest) as z: z.extractall(dev)
 outs=[]; tests=sorted((SOURCE/'tests').glob('*.py'))
 for t in tests:
  q=subprocess.run([sys.executable,str(t)],cwd=SOURCE,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT); outs.append(f'===== {t.name} =====\n{q.stdout}')
  if q.returncode: (LOGS/'test.log').write_text('\n'.join(outs),encoding='utf-8'); raise SystemExit(f'test failed: {t.name}')
 (LOGS/'test.log').write_text('\n'.join(outs),encoding='utf-8')
 env={'DOTNET_CLI_UI_LANGUAGE':'en','DOTNET_NOLOGO':'1'}; proj=SOURCE/'CrescentSetupDirector.csproj'; run(['dotnet','--info'],SOURCE,LOGS/'dotnet-info.log',env); run(['dotnet','restore',str(proj),'--locked-mode'],SOURCE,LOGS/'restore.log',env); run(['dotnet','build',str(proj),'-c','Release','--no-restore'],SOURCE,LOGS/'build.log',env)
 dll=min([p for p in SOURCE.rglob('CrescentSetupDirector.dll') if 'obj' not in p.parts],key=lambda p:len(p.parts)); out=dll.parent
 for n in ['CrescentSetupDirector.dll','CrescentSetupDirector.deps.json','CrescentSetupDirector.json']:
  p=out/n
  if not p.exists(): p=next(x for x in SOURCE.rglob(n) if 'obj' not in x.parts)
  shutil.copy2(p,PLUGIN/n)
 meta=json.loads((PLUGIN/'CrescentSetupDirector.json').read_text(encoding='utf-8-sig'))
 if meta.get('AssemblyVersion')!='0.2.5.0' or meta.get('DalamudApiLevel')!=15: raise SystemExit(f'bad manifest {meta}')
 srczip=ART/'source_v0.2.5_verified.zip'
 with zipfile.ZipFile(srczip,'w',zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=False) as z:
  for p in sorted(SOURCE.rglob('*')):
   rel=p.relative_to(SOURCE)
   if p.is_file() and not any(x in {'bin','obj','__pycache__'} for x in rel.parts): z.write(p,Path('source')/rel)
 build=(LOGS/'build.log').read_text(encoding='utf-8',errors='replace'); proof={'version':VERSION,'build_id':BUILD_ID,'target':'net10.0-windows / Dalamud API 15','tests_passed':len(tests),'test_count':len(tests),'build_zero_warnings':'0 Warning(s)' in build,'build_zero_errors':'0 Error(s)' in build,'source_zip_sha256':sha(srczip),'files':{p.name:{'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(PLUGIN.iterdir())}}
 (REPORTS/'BUILD_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(proof,ensure_ascii=False,indent=2))
 if not proof['build_zero_warnings'] or not proof['build_zero_errors']: raise SystemExit('nonzero build diagnostics')
if __name__=='__main__': main()
