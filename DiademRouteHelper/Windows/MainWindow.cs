using Dalamud.Bindings.ImGui;
using Dalamud.Interface.Windowing;
using System;
using System.Linq;
using System.Numerics;

namespace DiademRouteHelper.Windows;

public sealed class MainWindow : Window, IDisposable
{
    private readonly Plugin plugin;
    private uint selectedInventoryItemId;

    public MainWindow(Plugin plugin) : base("ディアデム採集ナビ##DiademRouteHelperMain")
    {
        this.plugin = plugin;
        SizeConstraints = new WindowSizeConstraints { MinimumSize = new Vector2(520, 460), MaximumSize = new Vector2(float.MaxValue, float.MaxValue) };
    }

    public void Dispose() { }

    public override void Draw()
    {
        if (!ImGui.BeginTabBar("MainTabs")) return;
        if (ImGui.BeginTabItem("ナビ")) { DrawNavigation(); ImGui.EndTabItem(); }
        if (ImGui.BeginTabItem("ルート編集")) { DrawRouteEditor(); ImGui.EndTabItem(); }
        if (ImGui.BeginTabItem("取得数")) { DrawTracker(); ImGui.EndTabItem(); }
        if (ImGui.BeginTabItem("設定")) { DrawSettings(); ImGui.EndTabItem(); }
        ImGui.EndTabBar();
    }

    private void DrawNavigation()
    {
        var player = Plugin.ObjectTable.LocalPlayer;
        var point = plugin.CurrentWaypoint;
        if (player is null) { ImGui.TextDisabled("キャラクターが読み込まれていないわ。"); return; }
        if (point is null) { ImGui.TextWrapped("ルートが空よ。採集地点で現在地を追加しなさい。"); return; }

        var distance = NavigationMath.HorizontalDistance(player.Position, point);
        ImGui.Text($"地点 {plugin.Configuration.CurrentWaypointIndex + 1} / {plugin.Configuration.Waypoints.Count}");
        ImGui.TextUnformatted(point.Name);
        ImGui.Separator();
        if (point.TerritoryId != Plugin.ClientState.TerritoryType)
            ImGui.TextColored(new Vector4(1f, 0.55f, 0.2f, 1f), "別エリアの地点よ。");
        else if (distance <= plugin.Configuration.ArrivalDistance)
            ImGui.TextColored(new Vector4(0.35f, 1f, 0.45f, 1f), $"到着圏内 {distance:F1}m");
        else
            ImGui.Text($"方角: {NavigationMath.WorldDirection(player.Position, point)}   距離: {distance:F1}m");

        if (ImGui.Button("◀ 前の地点")) plugin.PreviousWaypoint();
        ImGui.SameLine();
        if (ImGui.Button("次の地点 ▶")) plugin.NextWaypoint();
        ImGui.TextDisabled("移動、ターゲット、採集、地点切替はすべて手動よ。");
    }

    private void DrawRouteEditor()
    {
        if (ImGui.Button("現在地をルートへ追加")) plugin.AddCurrentPositionWaypoint();
        ImGui.Separator();

        var remove = -1;
        var up = -1;
        var down = -1;
        for (var i = 0; i < plugin.Configuration.Waypoints.Count; i++)
        {
            var point = plugin.Configuration.Waypoints[i];
            ImGui.PushID(i);
            if (ImGui.Selectable($"{i + 1}. {point.Name}##select", i == plugin.Configuration.CurrentWaypointIndex))
            {
                plugin.Configuration.CurrentWaypointIndex = i;
                plugin.Configuration.Save();
            }
            var name = point.Name;
            ImGui.SetNextItemWidth(220);
            if (ImGui.InputText("名前", ref name, 80)) { point.Name = name; plugin.Configuration.Save(); }
            ImGui.TextDisabled($"T:{point.TerritoryId} X:{point.X:F1} Y:{point.Y:F1} Z:{point.Z:F1}");
            if (ImGui.SmallButton("上へ")) up = i;
            ImGui.SameLine();
            if (ImGui.SmallButton("下へ")) down = i;
            ImGui.SameLine();
            if (ImGui.SmallButton("現在地で更新"))
            {
                var player = Plugin.ObjectTable.LocalPlayer;
                if (player is not null)
                {
                    point.TerritoryId = Plugin.ClientState.TerritoryType;
                    point.X = player.Position.X; point.Y = player.Position.Y; point.Z = player.Position.Z;
                    plugin.Configuration.Save();
                }
            }
            ImGui.SameLine();
            if (ImGui.SmallButton("削除")) remove = i;
            ImGui.Separator();
            ImGui.PopID();
        }

        if (up > 0) Swap(up, up - 1);
        else if (down >= 0 && down < plugin.Configuration.Waypoints.Count - 1) Swap(down, down + 1);
        if (remove >= 0)
        {
            plugin.Configuration.Waypoints.RemoveAt(remove);
            plugin.ClampWaypointIndex();
            plugin.Configuration.Save();
        }
    }

    private void DrawTracker()
    {
        var totals = InventoryHelper.GetMainInventoryTotals();
        var available = totals.Keys.Where(id => plugin.Configuration.TrackedItems.All(t => t.ItemId != id))
            .Select(id => new { Id = id, Name = InventoryHelper.GetItemName(id), Quantity = totals[id] })
            .OrderBy(x => x.Name, StringComparer.CurrentCulture).ToList();

        var preview = selectedInventoryItemId == 0 ? "持ち物から素材を選択" : $"{InventoryHelper.GetItemName(selectedInventoryItemId)} x{totals.GetValueOrDefault(selectedInventoryItemId)}";
        ImGui.SetNextItemWidth(330);
        if (ImGui.BeginCombo("##inventoryItem", preview))
        {
            foreach (var item in available)
                if (ImGui.Selectable($"{item.Name} x{item.Quantity}##{item.Id}")) selectedInventoryItemId = item.Id;
            ImGui.EndCombo();
        }
        ImGui.SameLine();
        if (ImGui.Button("追跡へ追加") && selectedInventoryItemId != 0)
        {
            plugin.Configuration.TrackedItems.Add(new TrackedItem { ItemId = selectedInventoryItemId, Name = InventoryHelper.GetItemName(selectedInventoryItemId), BaselineQuantity = totals.GetValueOrDefault(selectedInventoryItemId) });
            selectedInventoryItemId = 0;
            plugin.Configuration.Save();
        }
        if (ImGui.Button("セッション開始 / リセット"))
        {
            foreach (var tracked in plugin.Configuration.TrackedItems) tracked.BaselineQuantity = totals.GetValueOrDefault(tracked.ItemId);
            plugin.Configuration.SessionStartedUtc = DateTime.UtcNow;
            plugin.Configuration.Save();
        }

        var elapsed = DateTime.UtcNow - plugin.Configuration.SessionStartedUtc;
        var hours = Math.Max(elapsed.TotalHours, 1.0 / 3600.0);
        ImGui.Text($"経過: {elapsed:hh\\:mm\\:ss}");
        var remove = -1;
        for (var i = 0; i < plugin.Configuration.TrackedItems.Count; i++)
        {
            var tracked = plugin.Configuration.TrackedItems[i];
            var current = totals.GetValueOrDefault(tracked.ItemId);
            var gained = current - tracked.BaselineQuantity;
            ImGui.PushID(i);
            ImGui.Text($"{tracked.Name} 現在 {current} / 取得 {gained:+#;-#;0} / 時給 {gained / hours:F1}");
            ImGui.SameLine();
            if (ImGui.SmallButton("削除")) remove = i;
            ImGui.PopID();
        }
        if (remove >= 0) { plugin.Configuration.TrackedItems.RemoveAt(remove); plugin.Configuration.Save(); }
    }

    private void DrawSettings()
    {
        var overlay = plugin.Configuration.OverlayEnabled;
        if (ImGui.Checkbox("画面上にナビを表示", ref overlay)) { plugin.Configuration.OverlayEnabled = overlay; plugin.Configuration.Save(); }
        var territoryOnly = plugin.Configuration.OnlyShowOverlayInRouteTerritory;
        if (ImGui.Checkbox("同じエリアのときだけ表示", ref territoryOnly)) { plugin.Configuration.OnlyShowOverlayInRouteTerritory = territoryOnly; plugin.Configuration.Save(); }
        var distance = plugin.Configuration.ArrivalDistance;
        if (ImGui.SliderFloat("到着判定距離", ref distance, 1f, 20f, "%.1fm")) { plugin.Configuration.ArrivalDistance = distance; plugin.Configuration.Save(); }
        ImGui.Separator();
        ImGui.TextWrapped("/dnav、/dnav next、/dnav prev、/dnav add が使えるわ。自動操作は一切なしよ。");
    }

    private void Swap(int a, int b)
    {
        (plugin.Configuration.Waypoints[a], plugin.Configuration.Waypoints[b]) = (plugin.Configuration.Waypoints[b], plugin.Configuration.Waypoints[a]);
        if (plugin.Configuration.CurrentWaypointIndex == a) plugin.Configuration.CurrentWaypointIndex = b;
        else if (plugin.Configuration.CurrentWaypointIndex == b) plugin.Configuration.CurrentWaypointIndex = a;
        plugin.Configuration.Save();
    }
}
