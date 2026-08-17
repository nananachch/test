using Dalamud.Game.Inventory;
using Lumina.Excel.Sheets;
using System.Collections.Generic;

namespace DiademRouteHelper;

internal static class InventoryHelper
{
    private static readonly GameInventoryType[] MainInventoryTypes =
    {
        GameInventoryType.Inventory1,
        GameInventoryType.Inventory2,
        GameInventoryType.Inventory3,
        GameInventoryType.Inventory4,
    };

    internal static Dictionary<uint, int> GetMainInventoryTotals()
    {
        var result = new Dictionary<uint, int>();
        foreach (var inventoryType in MainInventoryTypes)
        {
            foreach (var item in Plugin.GameInventory.GetInventoryItems(inventoryType))
            {
                if (item.IsEmpty || item.BaseItemId == 0)
                    continue;

                result.TryGetValue(item.BaseItemId, out var current);
                result[item.BaseItemId] = current + item.Quantity;
            }
        }
        return result;
    }

    internal static string GetItemName(uint itemId)
    {
        return Plugin.DataManager.GetExcelSheet<Item>().TryGetRow(itemId, out var item)
            ? item.Name.ToString()
            : $"Item {itemId}";
    }
}
