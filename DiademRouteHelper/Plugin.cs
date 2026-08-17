using Dalamud.Game.ClientState.Objects.Enums;
using Dalamud.Game.ClientState.Objects.Types;
using Dalamud.Game.Command;
using Dalamud.Interface.ImGuiNotification;
using Dalamud.Interface.Windowing;
using Dalamud.IoC;
using Dalamud.Plugin;
using Dalamud.Plugin.Services;
using DiademRouteHelper.Windows;
using System;
using System.Linq;
using System.Numerics;

namespace DiademRouteHelper;

public sealed class Plugin : IDalamudPlugin
{
    private const string CommandName = "/dnav";

    [PluginService] internal static IDalamudPluginInterface PluginInterface { get; private set; } = null!;
    [PluginService] internal static ICommandManager CommandManager { get; private set; } = null!;
    [PluginService] internal static IClientState ClientState { get; private set; } = null!;
    [PluginService] internal static IObjectTable ObjectTable { get; private set; } = null!;
    [PluginService] internal static IGameInventory GameInventory { get; private set; } = null!;
    [PluginService] internal static IDataManager DataManager { get; private set; } = null!;
    [PluginService] internal static IGameGui GameGui { get; private set; } = null!;
    [PluginService] internal static ITargetManager TargetManager { get; private set; } = null!;
    [PluginService] internal static IFramework Framework { get; private set; } = null!;
    [PluginService] internal static INotificationManager NotificationManager { get; private set; } = null!;

    internal Configuration Configuration { get; }
    internal WindowSystem WindowSystem { get; } = new("GatheringAssistant");
    internal float? LowestEquipmentConditionPercent { get; private set; }

    private readonly MainWindow mainWindow;
    private readonly OverlayWindow overlayWindow;
    private DateTime nextDurabilityCheckUtc = DateTime.MinValue;
    private bool durabilityWasLow;
    private bool routeArrivalLatch;

    public Plugin()
    {
        Configuration = PluginInterface.GetPluginConfig() as Configuration ?? new Configuration();
        ClampWaypointIndex();

        mainWindow = new MainWindow(this);
        overlayWindow = new OverlayWindow(this) { IsOpen = true };
        WindowSystem.AddWindow(mainWindow);
        WindowSystem.AddWindow(overlayWindow);

        CommandManager.AddHandler(CommandName, new CommandInfo(OnCommand)
        {
            HelpMessage = "開閉: /dnav | 次: /dnav next | 前: /dnav prev | 現在地追加: /dnav add | 対象採集地点追加: /dnav addtarget",
        });

        Framework.Update += OnFrameworkUpdate;
        PluginInterface.UiBuilder.Draw += WindowSystem.Draw;
        PluginInterface.UiBuilder.OpenMainUi += ToggleMainUi;
        PluginInterface.UiBuilder.OpenConfigUi += ToggleMainUi;
    }

    public void Dispose()
    {
        Framework.Update -= OnFrameworkUpdate;
        PluginInterface.UiBuilder.Draw -= WindowSystem.Draw;
        PluginInterface.UiBuilder.OpenMainUi -= ToggleMainUi;
        PluginInterface.UiBuilder.OpenConfigUi -= ToggleMainUi;
        CommandManager.RemoveHandler(CommandName);
        WindowSystem.RemoveAllWindows();
        mainWindow.Dispose();
        overlayWindow.Dispose();
    }

    internal void ToggleMainUi() => mainWindow.Toggle();

    internal GatheringTarget? NearestGatheringTarget =>
        Configuration.AutoNearestGatheringPoint ? FindNearestGatheringTarget() : null;

    internal GatheringTarget? FindNearestGatheringTarget()
    {
        var player = ObjectTable.LocalPlayer;
        if (player is null)
            return null;

        return ObjectTable.EventObjects
            .Where(obj => obj.ObjectKind == ObjectKind.GatheringPoint && obj.IsTargetable)
            .Select(obj => new
            {
                Object = obj,
                Distance = NavigationMath.HorizontalDistance(player.Position, obj.Position),
            })
            .OrderBy(x => x.Distance)
            .Select(x =>
            {
                var name = x.Object.Name.TextValue;
                if (string.IsNullOrWhiteSpace(name))
                    name = "採集地点";
                return new GatheringTarget(name, x.Object.Position, x.Object.BaseId, x.Object.GameObjectId);
            })
            .FirstOrDefault();
    }

    internal Waypoint? CurrentWaypoint
    {
        get
        {
            ClampWaypointIndex();
            return Configuration.Waypoints.Count == 0 ? null : Configuration.Waypoints[Configuration.CurrentWaypointIndex];
        }
    }

    internal void NextWaypoint()
    {
        if (Configuration.Waypoints.Count == 0)
            return;

        Configuration.CurrentWaypointIndex = (Configuration.CurrentWaypointIndex + 1) % Configuration.Waypoints.Count;
        Configuration.Save();
    }

    internal void PreviousWaypoint()
    {
        if (Configuration.Waypoints.Count == 0)
            return;

        Configuration.CurrentWaypointIndex--;
        if (Configuration.CurrentWaypointIndex < 0)
            Configuration.CurrentWaypointIndex = Configuration.Waypoints.Count - 1;
        Configuration.Save();
    }

    internal void AddCurrentPositionWaypoint()
    {
        var player = ObjectTable.LocalPlayer;
        if (player is null)
            return;

        AddWaypoint($"地点 {Configuration.Waypoints.Count + 1}", player.Position);
    }

    internal void AddNearestGatheringPointWaypoint()
    {
        var target = FindNearestGatheringTarget();
        if (target is null)
        {
            Notify("採取補助", "現在読み込まれている採集地点がないわ。", NotificationType.Warning);
            return;
        }

        AddWaypoint(target.Name, target.Position);
    }

    internal void AddTargetedGatheringPointWaypoint()
    {
        var target = TargetManager.Target;
        if (target is null || target.ObjectKind != ObjectKind.GatheringPoint)
        {
            Notify("採取補助", "採集地点をターゲットしてから追加しなさい。", NotificationType.Warning);
            return;
        }

        var name = target.Name.TextValue;
        if (string.IsNullOrWhiteSpace(name))
            name = "採集地点";
        AddWaypoint(name, target.Position);
    }

    private void AddWaypoint(string name, Vector3 position)
    {
        var duplicate = Configuration.Waypoints.Any(point =>
            point.TerritoryId == ClientState.TerritoryType &&
            NavigationMath.HorizontalDistance(position, point) <= 1.5f);

        if (duplicate)
        {
            Notify("採取補助", "その地点はすでにルートへ登録されているわ。", NotificationType.Info);
            return;
        }

        Configuration.Waypoints.Add(new Waypoint
        {
            Name = name,
            TerritoryId = ClientState.TerritoryType,
            X = position.X,
            Y = position.Y,
            Z = position.Z,
        });
        Configuration.CurrentWaypointIndex = Configuration.Waypoints.Count - 1;
        Configuration.Save();
        Notify("採取補助", $"{name} をルートへ追加したわ。", NotificationType.Success);
    }

    internal void ClampWaypointIndex()
    {
        if (Configuration.Waypoints.Count == 0)
        {
            Configuration.CurrentWaypointIndex = 0;
            return;
        }

        Configuration.CurrentWaypointIndex = Math.Clamp(
            Configuration.CurrentWaypointIndex,
            0,
            Configuration.Waypoints.Count - 1);
    }

    private void OnFrameworkUpdate(IFramework framework)
    {
        UpdateRouteProgress();

        var now = DateTime.UtcNow;
        if (now < nextDurabilityCheckUtc)
            return;

        nextDurabilityCheckUtc = now.AddSeconds(5);
        UpdateDurabilityReminder();
    }

    private void UpdateRouteProgress()
    {
        if (Configuration.AutoNearestGatheringPoint ||
            !Configuration.AutoAdvanceRoute ||
            Configuration.Waypoints.Count < 2)
        {
            routeArrivalLatch = false;
            return;
        }

        var player = ObjectTable.LocalPlayer;
        var waypoint = CurrentWaypoint;
        if (player is null || waypoint is null || waypoint.TerritoryId != ClientState.TerritoryType)
        {
            routeArrivalLatch = false;
            return;
        }

        var arrived = NavigationMath.HorizontalDistance(player.Position, waypoint) <= Configuration.ArrivalDistance;
        if (!arrived)
        {
            routeArrivalLatch = false;
            return;
        }

        if (routeArrivalLatch)
            return;

        routeArrivalLatch = true;
        NextWaypoint();
    }

    private void UpdateDurabilityReminder()
    {
        if (!Configuration.DurabilityReminderEnabled)
        {
            LowestEquipmentConditionPercent = null;
            durabilityWasLow = false;
            return;
        }

        LowestEquipmentConditionPercent = EquipmentDurabilityHelper.GetLowestEquippedConditionPercent();
        var isLow = LowestEquipmentConditionPercent is float percent &&
                    percent < Configuration.DurabilityThresholdPercent;

        if (isLow && !durabilityWasLow)
        {
            Notify(
                "装備耐久が低下",
                $"装備耐久の最低値が {LowestEquipmentConditionPercent:0.#}% よ。修理しなさい。",
                NotificationType.Warning,
                TimeSpan.FromSeconds(12));
        }

        durabilityWasLow = isLow;
    }

    private static void Notify(
        string title,
        string content,
        NotificationType type,
        TimeSpan? duration = null)
    {
        NotificationManager.AddNotification(new Notification
        {
            Title = title,
            Content = content,
            Type = type,
            InitialDuration = duration ?? TimeSpan.FromSeconds(5),
            Minimized = false,
        });
    }

    private void OnCommand(string command, string args)
    {
        switch (args.Trim().ToLowerInvariant())
        {
            case "next":
            case "n":
                NextWaypoint();
                break;
            case "prev":
            case "previous":
            case "p":
                PreviousWaypoint();
                break;
            case "add":
                AddCurrentPositionWaypoint();
                break;
            case "addtarget":
            case "target":
                AddTargetedGatheringPointWaypoint();
                break;
            case "addnearest":
            case "nearest":
                AddNearestGatheringPointWaypoint();
                break;
            default:
                ToggleMainUi();
                break;
        }
    }
}
