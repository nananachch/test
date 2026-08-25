using Dalamud.Plugin.Services;
using Dalamud.Game.ClientState.Conditions;
using FFXIVClientStructs.FFXIV.Client.Game;
using FFXIVClientStructs.FFXIV.Client.Game.InstanceContent;

namespace CrescentSetupDirector;

public sealed unsafe class PhantomJobBridge
{
    public const byte BardJobId = 6;
    public const byte ThiefJobId = 12;

    private readonly Configuration config;
    private readonly ActionResolver resolver;
    private readonly IPluginLog log;

    public PhantomJobBridge(Configuration config, ActionResolver resolver, IPluginLog log)
    {
        this.config = config;
        this.resolver = resolver;
        this.log = log;
    }

    public uint CurrentJobId
    {
        get
        {
            var content = PublicContentOccultCrescent.GetInstance();
            var state = content == null ? null : PublicContentOccultCrescent.GetState();
            return state == null ? 0u : state->CurrentSupportJob;
        }
    }

    public bool IsInOccultCrescent
    {
        get
        {
            var game = GameMain.Instance();
            return game != null && game->CurrentTerritoryIntendedUseId == FFXIVClientStructs.FFXIV.Client.Enums.TerritoryIntendedUse.OccultCrescent;
        }
    }

    public bool TrySwitch(SupportJobChoice choice, out uint expectedJobId, out string reason)
    {
        if (!resolver.TryResolveSupportJob(choice, out expectedJobId, out var name))
        {
            reason = $"ファントムジョブを解決できません: {choice}";
            return false;
        }
        return TrySwitchToId(expectedJobId, name, out reason);
    }

    public bool TrySwitchToId(uint expectedJobId, string name, out string reason)
    {
        if (expectedJobId > byte.MaxValue)
        {
            reason = $"ファントムジョブIDが範囲外です: {expectedJobId}";
            return false;
        }
        if (CurrentJobId == expectedJobId)
        {
            reason = string.Empty;
            return true;
        }
        if (config.DryRun)
        {
            log.Information("[DRY RUN][PHANTOM JOB] {Name} id={Id}", name, expectedJobId);
            reason = string.Empty;
            return true;
        }
        if (!IsInOccultCrescent)
        {
            reason = "クレセントアイル外ではファントムジョブを変更しません。";
            return false;
        }
        if (Plugin.Condition[ConditionFlag.InCombat])
        {
            reason = "既に戦闘中のため、サポートジョブを変更できません。";
            return false;
        }

        var content = PublicContentOccultCrescent.GetInstance();
        if (content == null)
        {
            reason = "クレセントアイルのコンテンツ状態を取得できません。";
            return false;
        }

        var accepted = PublicContentOccultCrescent.ChangeSupportJob((byte)expectedJobId);
        log.Information("Phantom job change requested: {Name} id={Id} accepted={Accepted}", name, expectedJobId, accepted);
        reason = accepted ? string.Empty : "ゲーム側がファントムジョブ変更要求を受理しませんでした。";
        return accepted;
    }
}
