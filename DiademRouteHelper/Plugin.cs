using Dalamud.Game.ClientState.Objects.Enums;
using Dalamud.Game.Command;
using Dalamud.Interface.Windowing;
using Dalamud.IoC;
using Dalamud.Plugin;
using Dalamud.Plugin.Services;
using DiademRouteHelper.Windows;
using System;
using System.Linq;

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

    internal Configuration Configuration { get; }
    internal WindowSystem WindowSystem { get; } = new("DiademRouteHelper");

    private readonly MainWindow mainWindow;
    private readonly OverlayWindow overlayWindow;

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
            HelpMessage = "開閉: /dnav | 次: /dnav next | 前: /dnav prev | 現在地追加: /dnav add",
        });

        PluginInterface.UiBuilder.Draw += WindowSystem.Draw;
        PluginInterface.UiBuilder.OpenMainUi += ToggleMainUi;
        PluginInterface.UiBuilder.OpenConfigUi += ToggleMainUi;
    }

    public void Dispose()
    {
        PluginInterface.UiBuilder.Draw -= WindowSystem.Draw;
        PluginInterface.UiBuilder.OpenMainUi -= ToggleMainUi;
        PluginInterface.UiBuilder.OpenConfigUi -= ToggleMainUi;
        CommandManager.RemoveHandler(CommandName);
        WindowSystem.RemoveAllWindows();
        mainWindow.Dispose();
        overlayWindow.Dispose();
    }

    internal void ToggleMainUi() => mainWindow.Toggle();

    internal GatheringTarget? NearestGatheringTarget
    {
        get
        {
            if (!Configuration.AutoNearestGatheringPoint)
                return null;

            var player = ObjectTable.LocalPlayer;
            if (player is null)
                return null;

            return ObjectTable.EventObjects
                .Where(obj => obj.ObjectKind == ObjectKind.GatheringPoint && obj.IsTargetable)
                .Select(obj => new
                {
                    Object = obj,
                    Name = obj.Name.TextValue,
                    Distance = NavigationMath.HorizontalDistance(player.Position, obj.Position),
                })
                .Where(x => IsAllowedGatheringName(x.Name))
                .OrderBy(x => x.Distance)
                .Select(x => new GatheringTarget(x.Name, x.Object.Position, x.Object.BaseId, x.Object.GameObjectId))
                .FirstOrDefault();
        }
    }

    private bool IsAllowedGatheringName(string name)
    {
        var isBotany = name.Contains("草刈場", StringComparison.Ordinal);
        var isMining = name.Contains("採掘場", StringComparison.Ordinal);

        return Configuration.GatheringPointFilter switch
        {
            1 => isBotany,
            2 => isMining,
            _ => isBotany || isMining,
        };
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
        if (Configuration.Waypoints.Count == 0) return;
        Configuration.CurrentWaypointIndex = (Configuration.CurrentWaypointIndex + 1) % Configuration.Waypoints.Count;
        Configuration.Save();
    }

    internal void PreviousWaypoint()
    {
        if (Configuration.Waypoints.Count == 0) return;
        Configuration.CurrentWaypointIndex--;
        if (Configuration.CurrentWaypointIndex < 0)
            Configuration.CurrentWaypointIndex = Configuration.Waypoints.Count - 1;
        Configuration.Save();
    }

    internal void AddCurrentPositionWaypoint()
    {
        var player = ObjectTable.LocalPlayer;
        if (player is null) return;

        Configuration.Waypoints.Add(new Waypoint
        {
            Name = $"採集地点 {Configuration.Waypoints.Count + 1}",
            TerritoryId = ClientState.TerritoryType,
            X = player.Position.X,
            Y = player.Position.Y,
            Z = player.Position.Z,
        });
        Configuration.CurrentWaypointIndex = Configuration.Waypoints.Count - 1;
        Configuration.Save();
    }

    internal void ClampWaypointIndex()
    {
        if (Configuration.Waypoints.Count == 0)
        {
            Configuration.CurrentWaypointIndex = 0;
            return;
        }
        Configuration.CurrentWaypointIndex = Math.Clamp(Configuration.CurrentWaypointIndex, 0, Configuration.Waypoints.Count - 1);
    }

    private void OnCommand(string command, string args)
    {
        switch (args.Trim().ToLowerInvariant())
        {
            case "next": case "n": NextWaypoint(); break;
            case "prev": case "previous": case "p": PreviousWaypoint(); break;
            case "add": AddCurrentPositionWaypoint(); break;
            default: ToggleMainUi(); break;
        }
    }
}
