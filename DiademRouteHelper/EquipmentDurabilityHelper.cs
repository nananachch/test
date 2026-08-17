using Dalamud.Game.Inventory;

namespace DiademRouteHelper;

internal static class EquipmentDurabilityHelper
{
    private const float RawConditionPerPercent = 300f;
    private const uint SoulCrystalSlot = 13;

    internal static float? GetLowestEquippedConditionPercent()
    {
        float? lowest = null;

        foreach (var item in Plugin.GameInventory.GetInventoryItems(GameInventoryType.EquippedItems))
        {
            if (item.IsEmpty || item.BaseItemId == 0 || item.InventorySlot >= SoulCrystalSlot)
                continue;

            var percent = item.Condition / RawConditionPerPercent;
            if (lowest is null || percent < lowest.Value)
                lowest = percent;
        }

        return lowest;
    }
}
