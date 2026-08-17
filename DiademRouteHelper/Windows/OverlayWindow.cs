using Dalamud.Bindings.ImGui;
using Dalamud.Interface.Windowing;
using System;
using System.Numerics;

namespace DiademRouteHelper.Windows;

public sealed class OverlayWindow : Window, IDisposable
{
    private readonly Plugin plugin;

    public OverlayWindow(Plugin plugin)
        : base("採取補助##GatheringAssistantOverlay", ImGuiWindowFlags.AlwaysAutoResize | ImGuiWindowFlags.NoScrollbar | ImGuiWindowFlags.NoScrollWithMouse | ImGuiWindowFlags.NoCollapse | ImGuiWindowFlags.NoFocusOnAppearing)
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
        if (!plugin.Configuration.OverlayEnabled)
            return false;

        if (Plugin.ObjectTable.LocalPlayer is null)
            return false;

        if (plugin.LowestEquipmentConditionPercent is float condition &&
            condition < plugin.Configuration.DurabilityThresholdPercent)
            return true;

        if (plugin.NearestGatheringTarget is not null)
            return true;

        var waypoint = plugin.CurrentWaypoint;
        if (waypoint is null)
            return false;

        return !plugin.Configuration.OnlyShowOverlayInRouteTerritory ||
               waypoint.TerritoryId == Plugin.ClientState.TerritoryType;
    }

    public override void Draw()
    {
        var player = Plugin.ObjectTable.LocalPlayer;
        if (player is null)
            return;

        if (plugin.LowestEquipmentConditionPercent is float condition &&
            condition < plugin.Configuration.DurabilityThresholdPercent)
        {
            ImGui.TextColored(
                new Vector4(1f, 0.3f, 0.2f, 1f),
                $"装備耐久 {condition:0.#}%　修理しなさい");
            ImGui.Separator();
        }

        var target = plugin.NearestGatheringTarget;
        if (target is not null)
        {
            var distance = NavigationMath.HorizontalDistance(player.Position, target.Position);
            var direction = NavigationMath.WorldDirection(player.Position, target.Position);
            ImGui.TextColored(new Vector4(0.45f, 0.95f, 0.55f, 1f), "最寄り採集地点を自動追跡");
            ImGui.TextUnformatted(target.Name);
            ImGui.Text($"{direction}   {distance:F1}m");
            ImGui.TextDisabled("採取後は次に近い地点へ自動更新");

            if (plugin.Configuration.DrawWorldArrow)
                DrawArrowToWorldPosition(player.Position, target.Position);

            if (ImGui.SmallButton("設定"))
                plugin.ToggleMainUi();
            return;
        }

        var waypoint = plugin.CurrentWaypoint;
        if (waypoint is null)
        {
            ImGui.TextDisabled("読み込まれている採集地点も登録ルートもないわ。");
            if (ImGui.SmallButton("設定"))
                plugin.ToggleMainUi();
            return;
        }

        var waypointPosition = new Vector3(waypoint.X, waypoint.Y, waypoint.Z);
        var manualDistance = NavigationMath.HorizontalDistance(player.Position, waypoint);
        var manualDirection = NavigationMath.WorldDirection(player.Position, waypoint);
        ImGui.TextColored(new Vector4(0.55f, 0.8f, 1f, 1f), "登録ルートを周回");
        ImGui.Text($"{plugin.Configuration.CurrentWaypointIndex + 1}/{plugin.Configuration.Waypoints.Count}  {waypoint.Name}");

        if (manualDistance <= plugin.Configuration.ArrivalDistance)
            ImGui.TextColored(new Vector4(0.35f, 1f, 0.45f, 1f), $"到着  {manualDistance:F1}m");
        else
            ImGui.Text($"{manualDirection}   {manualDistance:F1}m");

        if (plugin.Configuration.DrawWorldArrow &&
            waypoint.TerritoryId == Plugin.ClientState.TerritoryType)
            DrawArrowToWorldPosition(player.Position, waypointPosition);

        if (ImGui.SmallButton("◀"))
            plugin.PreviousWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("▶"))
            plugin.NextWaypoint();
        ImGui.SameLine();
        if (ImGui.SmallButton("設定"))
            plugin.ToggleMainUi();
    }

    private static void DrawArrowToWorldPosition(Vector3 playerPosition, Vector3 targetPosition)
    {
        var levelTarget = new Vector3(targetPosition.X, playerPosition.Y, targetPosition.Z);

        if (!Plugin.GameGui.WorldToScreen(playerPosition, out var playerScreen, out _))
            return;
        if (!Plugin.GameGui.WorldToScreen(levelTarget, out var targetScreen, out _))
            return;

        var delta = targetScreen - playerScreen;
        if (delta.LengthSquared() < 4f)
            return;

        var direction = Vector2.Normalize(delta);
        var start = playerScreen + direction * 20f;
        var end = targetScreen - direction * 18f;
        var perpendicular = new Vector2(-direction.Y, direction.X);
        var color = ImGui.GetColorU32(new Vector4(0.25f, 1f, 0.45f, 0.92f));
        var drawList = ImGui.GetForegroundDrawList();

        drawList.AddLine(start, end, color, 4f);
        drawList.AddTriangleFilled(
            targetScreen,
            targetScreen - direction * 22f + perpendicular * 10f,
            targetScreen - direction * 22f - perpendicular * 10f,
            color);
    }
}
