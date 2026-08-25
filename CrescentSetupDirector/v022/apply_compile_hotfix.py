from pathlib import Path

p = Path(__file__).resolve().parent / "SOURCE" / "CombatAutomationBridge.cs"
s = p.read_text(encoding="utf-8")
old = '''            if (TrySetBmrForceDisabled(out var ipcError))
            {
                bmrAutorotationPauseSent = true;
            }
            else if (HasBmrCommand && ExecuteCustom(BmrAutorotationDisableCommand, "BMR Autorotation停止要求", out var commandError))
            {
                bmrAutorotationPauseSent = true;
            }
            else
            {
                var detail = HasBmrCommand ? commandError : "BMR /bmr が未検出です。";
'''
new = '''            var commandError = "BMR /bmr が未検出です。";
            if (TrySetBmrForceDisabled(out var ipcError))
            {
                bmrAutorotationPauseSent = true;
            }
            else if (HasBmrCommand && ExecuteCustom(BmrAutorotationDisableCommand, "BMR Autorotation停止要求", out commandError))
            {
                bmrAutorotationPauseSent = true;
            }
            else
            {
                var detail = commandError;
'''
if old not in s:
    raise SystemExit("Expected CombatAutomationBridge compile-hotfix target was not found")
p.write_text(s.replace(old, new), encoding="utf-8")
print("Applied CombatAutomationBridge definite-assignment hotfix")
