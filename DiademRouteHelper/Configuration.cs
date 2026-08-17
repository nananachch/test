using Dalamud.Configuration;
using System;
using System.Collections.Generic;

namespace DiademRouteHelper;

[Serializable]
public sealed class Configuration : IPluginConfiguration
{
    public int Version { get; set; } = 3;
    public List<Waypoint> Waypoints { get; set; } = new();
    public int CurrentWaypointIndex { get; set; }
    public List<TrackedItem> TrackedItems { get; set; } = new();
    public DateTime SessionStartedUtc { get; set; } = DateTime.UtcNow;
    public bool OverlayEnabled { get; set; } = true;
    public bool OnlyShowOverlayInRouteTerritory { get; set; } = true;
    public float ArrivalDistance { get; set; } = 6.0f;
    public bool AutoNearestGatheringPoint { get; set; } = true;
    public int GatheringPointFilter { get; set; } = 0;
    public bool DrawWorldArrow { get; set; } = true;
    public bool AutoAdvanceRoute { get; set; } = true;
    public bool DurabilityReminderEnabled { get; set; } = true;
    public float DurabilityThresholdPercent { get; set; } = 10.0f;

    public void Save() => Plugin.PluginInterface.SavePluginConfig(this);
}
