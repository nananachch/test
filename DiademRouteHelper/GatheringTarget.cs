using System.Numerics;

namespace DiademRouteHelper;

internal sealed record GatheringTarget(
    string Name,
    Vector3 Position,
    uint BaseId,
    ulong GameObjectId);
