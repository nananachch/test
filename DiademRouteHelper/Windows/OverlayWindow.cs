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
        if (Plugin.ObjectTable.LocalPlayer is null) return false;
        if (plugin.NearestGatheringTarget is not null) return true;

        var waypoint = plugin.CurrentWaypoint;
        if (waypoint is null) return false;
        return !plugin.Configuration.OnlyShowOverlayInRouteTerritory || waypoint.TerritoryId == Plugin.ClientState.TerritoryType;
    }

    public override void Draw()
    {
        var player = Plugin.ObjectTable.LocalPlayer;
        if (player is null) return;

        var target = plugin.NearestGatheringTarget;
        if (target is not null)
        {
            var distance = NavigationMath.HorizontalDistance(player.Position, target.Position);
            var direction = NavigationMath.WorldDirection(player.Position, target.Position);
            ImGui.TextColored(new Vector4(0.45f, 0.95f, 0.55f, 1f), "最寄りを自動追跡");
            ImGui.TextUnformatted(target.Name);
            ImGui.Text($"{direction}   {distance:F1}m");
            ImGui.TextDisabled("採取後は次に近い地点へ自動更新");

            if (plugin.Configuration.DrawWorldArrow)
                DrawArrowToWorldPosition(target.Position);

            if (ImGui.SmallButton("設定")) plugin.ToggleMainUi();
            return;
        }

        var waypoint = plugin.CurrentWaypoint;
        if (waypoint is null)
        {
            ImGui.TextDisabled("読み込まれている採集地点がないわ。");
            if (ImGui.SmallButton("設定")) plugin.ToggleMainUi();
            return;
        }

        var manualDistance = NavigationMath.HorizontalDistance(player.Position, waypoint);
        var manualDirection = NavigationMath.WorldDirection(player.Position, waypoint);
        ImGui.Text($"{plugin.Configuration.CurrentWaypointIndex + 1}/{plugin.Configuration.Waypoints.Count}  {waypoint.Name}");

        if (manualDistance <= plugin.Configuration.ArrivalDistance)
            ImGui.TextColored(new Vector4(0.35f, 1f, 0.45f, 1f), $"到着  {manualDistance:F1}m");
        else
            ImGui.Text($"{manualDirection}   {manualDistance:F1}m");

        if (ImGui.SmallButton("◀")) plugin.PreviousWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("▶")) plugin.NextWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("設定")) plugin.ToggleMainUi();
    }

    private static void DrawArrowToWorldPosition(Vector3 worldPosition)
    {
        if (!Plugin.GameGui.WorldToScreen(worldPosition, out var targetScreen, out _))
            return;

        var viewport = ImGui.GetMainViewport();
        var center = viewport.Pos + (viewport.Size / 2f);
        var delta = targetScreen - center;
        if (delta.LengthSquared() < 1f)
            return;

        var direction = Vector2.Normalize(delta);
        var start = center + direction * 45f;
        var end = targetScreen - direction * 18f;
        var perpendicular = new Vector2(-direction.Y, direction.X);
        var color = ImGui.GetColorU32(new Vector4(0.25f, 1f, 0.45f, 0.9f));
        var drawList = ImGui.GetForegroundDrawList();

        drawList.AddLine(start, end, color, 4f);
        drawList.AddTriangleFilled(
            targetScreen,
            targetScreen - direction * 22f + perpendicular * 10f,
            targetScreen - direction * 22f - perpendicular * 10f,
            color);
    }
}
