using System;

namespace DiademRouteHelper;

[Serializable]
public sealed class Waypoint
{
    public string Name { get; set; } = "採集地点";
    public uint TerritoryId { get; set; }
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}

[Serializable]
public sealed class TrackedItem
{
    public uint ItemId { get; set; }
    public string Name { get; set; } = "素材";
    public int BaselineQuantity { get; set; }
}
