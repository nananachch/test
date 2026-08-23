from pathlib import Path

p = Path(__file__).resolve().parent / "SOURCE" / "SetupEngine.cs"
s = p.read_text(encoding="utf-8")

replacements = [
    (
'''    public void EmergencyStop(string reason = "手動緊急停止")
    {
        diagnostics.Write($"[STOP] {reason}");
        automation.ResumeAll(reason);
        ClearActiveWorkflow();
    }
''',
'''    public void EmergencyStop(string reason = "手動緊急停止")
    {
        diagnostics.Write($"[STOP] {reason}");
        if (workflow == WorkflowKind.NormalFate)
            QueueOriginalSupportRestore(waitForFateEnd: false, "emergency-stop");
        automation.ResumeAll(reason);
        ClearActiveWorkflow();
    }
'''),
    (
'''    private void TryAutoStartNormalFate()
    {
        if (!config.AutoStartInFateRange || !phantom.IsInOccultCrescent)
''',
'''    private void TryAutoStartNormalFate()
    {
        if (pendingRestoreSupportJob != 0)
            return;
        if (!config.AutoStartInFateRange || !phantom.IsInOccultCrescent)
'''),
    (
'''    private void TryAutoStartCriticalEncounter()
    {
        if (!config.CeAutoSetupEnabled || !phantom.IsInOccultCrescent)
''',
'''    private void TryAutoStartCriticalEncounter()
    {
        if (pendingRestoreSupportJob != 0)
            return;
        if (!config.CeAutoSetupEnabled || !phantom.IsInOccultCrescent)
'''),
    (
'''            if (config.RestoreOriginalSupportAfterFate && originalSupportJob != 0 && originalSupportJob != phantom.CurrentJobId)
            {
                pendingRestoreSupportJob = originalSupportJob;
                pendingRestoreFateId = activeFate?.FateId ?? 0;
                restoreAttempts = 0;
                restoreSafeSince = default;
                diagnostics.Write($"[RESTORE-QUEUED] fate={pendingRestoreFateId} support={pendingRestoreSupportJob}");
            }
''',
'''            QueueOriginalSupportRestore(waitForFateEnd: true, "normal-fate-complete");
'''),
    (
'''    private void TickPendingSupportRestore()
    {
        if (pendingRestoreSupportJob == 0 || workflow != WorkflowKind.None && workflow != WorkflowKind.NormalFate)
            return;
''',
'''    private void TickPendingSupportRestore()
    {
        // Never change support jobs while any setup workflow owns control.
        if (pendingRestoreSupportJob == 0 || workflow != WorkflowKind.None)
            return;
'''),
    (
'''    private void Fail(string reason, string? key = null)
    {
        if (state == SetupState.Failed) return;
        failureReason = reason;
''',
'''    private void Fail(string reason, string? key = null)
    {
        if (state == SetupState.Failed) return;
        if (workflow == WorkflowKind.NormalFate)
            QueueOriginalSupportRestore(waitForFateEnd: false, "normal-fate-failed");
        failureReason = reason;
'''),
    (
'''    private void ClearActiveWorkflow()
    {
''',
'''    private void QueueOriginalSupportRestore(bool waitForFateEnd, string reason)
    {
        if (!config.RestoreOriginalSupportAfterFate || originalSupportJob == 0 || originalSupportJob == phantom.CurrentJobId)
            return;
        pendingRestoreSupportJob = originalSupportJob;
        pendingRestoreFateId = waitForFateEnd ? activeFate?.FateId ?? (ushort)0 : (ushort)0;
        restoreAttempts = 0;
        restoreSafeSince = default;
        diagnostics.Write($"[RESTORE-QUEUED] reason={reason} fate={pendingRestoreFateId} support={pendingRestoreSupportJob}");
    }

    private void ClearActiveWorkflow()
    {
'''),
]

for old, new in replacements:
    if old not in s:
        raise SystemExit(f"Patch anchor not found: {old.splitlines()[0]}")
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("Applied final support-restore transaction patch")
