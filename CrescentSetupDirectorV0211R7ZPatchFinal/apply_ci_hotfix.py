from pathlib import Path

p = Path(r"CrescentSetupDirectorV0211R7ZPatchFinal/ci_build.py")
s = p.read_text(encoding="utf-8")
old_id = "CSD_V0211_API15_NET10_CE_BELL_GATE_SUPPORT_PRIORITY_R7_20260828"
new_id = "CSD_V0211_API15_NET10_ALL_REPORTED_BUGFIX_R7_20260828"
if old_id not in s:
    raise SystemExit("expected pre-hotfix Build ID not found")
s = s.replace(old_id, new_id, 1)
needle = '        archive.extractall(source, filter="data")\n'
insertion = needle + '''    setup_engine = source / "SetupEngine.cs"\n    setup_text = setup_engine.read_text(encoding="utf-8")\n    broken = "            && (magicPotLastResumeReassertUtc == default || (DateTime.UtcNow - magicPotLastResumeReassertUtc).TotalSeconds >= 4)\\n        {"\n    fixed = "            && (magicPotLastResumeReassertUtc == default || (DateTime.UtcNow - magicPotLastResumeReassertUtc).TotalSeconds >= 4))\\n        {"\n    if broken not in setup_text:\n        raise SystemExit("expected SetupEngine compile hotfix target not found")\n    setup_engine.write_text(setup_text.replace(broken, fixed, 1), encoding="utf-8")\n'''
if needle not in s:
    raise SystemExit("source extraction marker not found")
s = s.replace(needle, insertion, 1)
p.write_text(s, encoding="utf-8")
