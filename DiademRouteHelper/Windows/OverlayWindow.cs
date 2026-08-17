using Dalamud.Bindings.ImGui;
using Dalamud.Interface.Windowing;
using System;
using System.Numerics;

namespace DiademRouteHelper.Windows;

public sealed class OverlayWindow : Window, IDisposable
{
    private readonly Plugin plugin;

    public OverlayWindow(Plugin plugin)
        : base("採集ナビ##DiademRouteHelperOverlay", ImGuiWindowFlags.AlwaysAutoResize | ImGuiWindowFlags.NoScrollbar | ImGuiWindowFlags.NoScrollWithMouse | ImGuiWindowFlags.NoCollapse | ImGuiWindowFlags.NoFocusOnAppearing)
    {
        this.plugin = plugin;
        ShowCloseButton = false;
        AllowPinning = true;
        AllowClickthrough = true;
        RespectCloseHotkey = false;
        BgAlpha = 0.78f;
    }

    public void Dispose() { }

    public override bool DrawConditions()
    {
        if (!plugin.Configuration.OverlayEnabled) return false;
        var waypoint = plugin.CurrentWaypoint;
        var player = Plugin.ObjectTable.LocalPlayer;
        if (waypoint is null || player is null) return false;
        return !plugin.Configuration.OnlyShowOverlayInRouteTerritory || waypoint.TerritoryId == Plugin.ClientState.TerritoryType;
    }

    public override void Draw()
    {
        var waypoint = plugin.CurrentWaypoint;
        var player = Plugin.ObjectTable.LocalPlayer;
        if (waypoint is null || player is null) return;

        var distance = NavigationMath.HorizontalDistance(player.Position, waypoint);
        var direction = NavigationMath.WorldDirection(player.Position, waypoint);
        ImGui.Text($"{plugin.Configuration.CurrentWaypointIndex + 1}/{plugin.Configuration.Waypoints.Count}  {waypoint.Name}");

        if (distance <= plugin.Configuration.ArrivalDistance)
            ImGui.TextColored(new Vector4(0.35f, 1f, 0.45f, 1f), $"到着  {distance:F1}m");
        else
            ImGui.Text($"{direction}   {distance:F1}m");

        if (ImGui.SmallButton("◀")) plugin.PreviousWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("▶")) plugin.NextWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("設定")) plugin.ToggleMainUi();
    }
}
