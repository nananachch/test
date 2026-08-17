using Dalamud.Bindings.ImGui;
using Dalamud.Interface.Windowing;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace DiademRouteHelper.Windows;

public sealed class MainWindow : Window, IDisposable
{
    private readonly Plugin plugin;
    private uint selectedInventoryItemId;

    public MainWindow(Plugin plugin) : base("採取補助##GatheringAssistantMain")
    {
        this.plugin = plugin;
        SizeConstraints = new WindowSizeConstraints
        {
            MinimumSize = new Vector2(540, 500),
            MaximumSize = new Vector2(float.MaxValue, float.MaxValue),
        };
    }

    public void Dispose() { }

    public override void Draw()
    {
        if (!ImGui.BeginTabBar("MainTabs"))
            return;

        if (ImGui.BeginTabItem("ナビ"))
        {
            DrawNavigation();
            ImGui.EndTabItem();
        }

        if (ImGui.BeginTabItem("ルート編集"))
        {
            DrawRouteEditor();
            ImGui.EndTabItem();
        }

        if (ImGui.BeginTabItem("取得数"))
        {
            DrawTracker();
            ImGui.EndTabItem();
        }

        if (ImGui.BeginTabItem("設定"))
        {
            DrawSettings();
            ImGui.EndTabItem();
        }

        ImGui.EndTabBar();
    }

    private void DrawNavigation()
    {
        var player = Plugin.ObjectTable.LocalPlayer;
        if (player is null)
        {
            ImGui.TextDisabled("キャラクターが読み込まれていないわ。");
            return;
        }

        if (plugin.Configuration.AutoNearestGatheringPoint)
        {
            ImGui.TextColored(new Vector4(0.45f, 0.95f, 0.55f, 1f), "モード：最寄り採集地点");
            ImGui.TextWrapped("名称を問わず、現在読み込まれている採集地点の中から一番近いものを案内するわ。");

            var target = plugin.FindNearestGatheringTarget();
            if (target is null)
            {
                ImGui.Separator();
                ImGui.TextDisabled("現在読み込まれている採集地点がないわ。");
                return;
            }

            var distance = NavigationMath.HorizontalDistance(player.Position, target.Position);
            ImGui.Separator();
            ImGui.TextUnformatted(target.Name);
            ImGui.Text($"方角: {NavigationMath.WorldDirection(player.Position, target.Position)}   距離: {distance:F1}m");

            if (ImGui.Button("この採集地点をルートへ追加"))
                plugin.AddNearestGatheringPointWaypoint();

            return;
        }

        ImGui.TextColored(new Vector4(0.55f, 0.8f, 1f, 1f), "モード：登録ルート周回");

        var point = plugin.CurrentWaypoint;
        if (point is null)
        {
            ImGui.TextWrapped("ルートが空よ。「ルート編集」で採集地点を登録しなさい。");
            return;
        }

        var distanceToPoint = NavigationMath.HorizontalDistance(player.Position, point);
        ImGui.Text($"地点 {plugin.Configuration.CurrentWaypointIndex + 1} / {plugin.Configuration.Waypoints.Count}");
        ImGui.TextUnformatted(point.Name);
        ImGui.Separator();

        if (point.TerritoryId != Plugin.ClientState.TerritoryType)
            ImGui.TextColored(new Vector4(1f, 0.55f, 0.2f, 1f), "別エリアの地点よ。");
        else if (distanceToPoint <= plugin.Configuration.ArrivalDistance)
            ImGui.TextColored(new Vector4(0.35f, 1f, 0.45f, 1f), $"到着圏内 {distanceToPoint:F1}m");
        else
            ImGui.Text($"方角: {NavigationMath.WorldDirection(player.Position, point)}   距離: {distanceToPoint:F1}m");

        if (ImGui.Button("◀ 前の地点"))
            plugin.PreviousWaypoint();
        ImGui.SameLine();
        if (ImGui.Button("次の地点 ▶"))
            plugin.NextWaypoint();

        ImGui.TextDisabled(
            plugin.Configuration.AutoAdvanceRoute
                ? "到着すると次の登録地点へ自動で案内先を切り替えるわ。"
                : "地点切り替えは手動よ。");
    }

    private void DrawRouteEditor()
    {
        if (ImGui.Button("ターゲット中の採集地点を追加"))
            plugin.AddTargetedGatheringPointWaypoint();

        ImGui.SameLine();
        if (ImGui.Button("最寄りの採集地点を追加"))
            plugin.AddNearestGatheringPointWaypoint();

        ImGui.SameLine();
        if (ImGui.Button("現在地を追加"))
            plugin.AddCurrentPositionWaypoint();

        ImGui.TextDisabled("採集地点を選んで登録しておけば、登録順に周回案内できるわ。");
        ImGui.Separator();

        var remove = -1;
        var up = -1;
        var down = -1;

        for (var i = 0; i < plugin.Configuration.Waypoints.Count; i++)
        {
            var point = plugin.Configuration.Waypoints[i];
            ImGui.PushID(i);

            if (ImGui.Selectable(
                    $"{i + 1}. {point.Name}##select",
                    i == plugin.Configuration.CurrentWaypointIndex))
            {
                plugin.Configuration.CurrentWaypointIndex = i;
                plugin.Configuration.Save();
            }

            var name = point.Name;
            ImGui.SetNextItemWidth(220);
            if (ImGui.InputText("名前", ref name, 80))
            {
                point.Name = name;
                plugin.Configuration.Save();
            }

            ImGui.TextDisabled($"T:{point.TerritoryId} X:{point.X:F1} Y:{point.Y:F1} Z:{point.Z:F1}");

            if (ImGui.SmallButton("上へ"))
                up = i;
            ImGui.SameLine();
            if (ImGui.SmallButton("下へ"))
                down = i;
            ImGui.SameLine();
            if (ImGui.SmallButton("現在地で更新"))
            {
                var player = Plugin.ObjectTable.LocalPlayer;
                if (player is not null)
                {
                    point.TerritoryId = Plugin.ClientState.TerritoryType;
                    point.X = player.Position.X;
                    point.Y = player.Position.Y;
                    point.Z = player.Position.Z;
                    plugin.Configuration.Save();
                }
            }

            ImGui.SameLine();
            if (ImGui.SmallButton("削除"))
                remove = i;

            ImGui.Separator();
            ImGui.PopID();
        }

        if (up > 0)
            Swap(up, up - 1);
        else if (down >= 0 && down < plugin.Configuration.Waypoints.Count - 1)
            Swap(down, down + 1);

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
        var available = totals.Keys
            .Where(id => plugin.Configuration.TrackedItems.All(t => t.ItemId != id))
            .Select(id => new
            {
                Id = id,
                Name = InventoryHelper.GetItemName(id),
                Quantity = totals[id],
            })
            .OrderBy(x => x.Name, StringComparer.CurrentCulture)
            .ToList();

        var preview = selectedInventoryItemId == 0
            ? "持ち物から素材を選択"
            : $"{InventoryHelper.GetItemName(selectedInventoryItemId)} x{totals.GetValueOrDefault(selectedInventoryItemId)}";

        ImGui.SetNextItemWidth(330);
        if (ImGui.BeginCombo("##inventoryItem", preview))
        {
            foreach (var item in available)
            {
                if (ImGui.Selectable($"{item.Name} x{item.Quantity}##{item.Id}"))
                    selectedInventoryItemId = item.Id;
            }

            ImGui.EndCombo();
        }

        ImGui.SameLine();
        if (ImGui.Button("追跡へ追加") && selectedInventoryItemId != 0)
        {
            plugin.Configuration.TrackedItems.Add(new TrackedItem
            {
                ItemId = selectedInventoryItemId,
                Name = InventoryHelper.GetItemName(selectedInventoryItemId),
                BaselineQuantity = totals.GetValueOrDefault(selectedInventoryItemId),
            });
            selectedInventoryItemId = 0;
            plugin.Configuration.Save();
        }

        if (ImGui.Button("セッション開始 / リセット"))
        {
            foreach (var tracked in plugin.Configuration.TrackedItems)
                tracked.BaselineQuantity = totals.GetValueOrDefault(tracked.ItemId);

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
            if (ImGui.SmallButton("削除"))
                remove = i;
            ImGui.PopID();
        }

        if (remove >= 0)
        {
            plugin.Configuration.TrackedItems.RemoveAt(remove);
            plugin.Configuration.Save();
        }
    }

    private void DrawSettings()
    {
        var autoNearest = plugin.Configuration.AutoNearestGatheringPoint;
        if (ImGui.Checkbox("読み込み中の最寄り採集地点を自動案内", ref autoNearest))
        {
            plugin.Configuration.AutoNearestGatheringPoint = autoNearest;
            plugin.Configuration.Save();
        }
        ImGui.TextDisabled("オフにすると登録ルートを案内するわ。採集地点の名称では判定しない。");

        var autoAdvance = plugin.Configuration.AutoAdvanceRoute;
        if (ImGui.Checkbox("登録地点へ到着したら次へ自動切り替え", ref autoAdvance))
        {
            plugin.Configuration.AutoAdvanceRoute = autoAdvance;
            plugin.Configuration.Save();
        }

        var overlay = plugin.Configuration.OverlayEnabled;
        if (ImGui.Checkbox("画面上にナビを表示", ref overlay))
        {
            plugin.Configuration.OverlayEnabled = overlay;
            plugin.Configuration.Save();
        }

        var arrow = plugin.Configuration.DrawWorldArrow;
        if (ImGui.Checkbox("キャラクター位置から矢印を表示", ref arrow))
        {
            plugin.Configuration.DrawWorldArrow = arrow;
            plugin.Configuration.Save();
        }

        var territoryOnly = plugin.Configuration.OnlyShowOverlayInRouteTerritory;
        if (ImGui.Checkbox("登録ルートと同じエリアのときだけ表示", ref territoryOnly))
        {
            plugin.Configuration.OnlyShowOverlayInRouteTerritory = territoryOnly;
            plugin.Configuration.Save();
        }

        var distance = plugin.Configuration.ArrivalDistance;
        if (ImGui.SliderFloat("到着判定距離", ref distance, 1f, 20f, "%.1fm"))
        {
            plugin.Configuration.ArrivalDistance = distance;
            plugin.Configuration.Save();
        }

        ImGui.Separator();

        var durability = plugin.Configuration.DurabilityReminderEnabled;
        if (ImGui.Checkbox("装備耐久の低下を通知", ref durability))
        {
            plugin.Configuration.DurabilityReminderEnabled = durability;
            plugin.Configuration.Save();
        }

        var threshold = plugin.Configuration.DurabilityThresholdPercent;
        if (ImGui.SliderFloat("耐久通知のしきい値", ref threshold, 1f, 50f, "%.0f%%"))
        {
            plugin.Configuration.DurabilityThresholdPercent = threshold;
            plugin.Configuration.Save();
        }

        if (plugin.LowestEquipmentConditionPercent is float currentCondition)
            ImGui.TextDisabled($"現在の最低耐久: {currentCondition:0.#}%");

        ImGui.Separator();
        ImGui.TextWrapped(
            "/dnav、/dnav next、/dnav prev、/dnav add、/dnav addtarget が使えるわ。"
            + "移動、ターゲット、採集、キー入力は自動化しない。");
    }

    private void Swap(int a, int b)
    {
        (plugin.Configuration.Waypoints[a], plugin.Configuration.Waypoints[b]) =
            (plugin.Configuration.Waypoints[b], plugin.Configuration.Waypoints[a]);

        if (plugin.Configuration.CurrentWaypointIndex == a)
            plugin.Configuration.CurrentWaypointIndex = b;
        else if (plugin.Configuration.CurrentWaypointIndex == b)
            plugin.Configuration.CurrentWaypointIndex = a;

        plugin.Configuration.Save();
    }
}
