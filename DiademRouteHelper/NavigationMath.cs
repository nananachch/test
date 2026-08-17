using System;
using System.Numerics;

namespace DiademRouteHelper;

internal static class NavigationMath
{
    internal static float HorizontalDistance(Vector3 from, Waypoint to)
    {
        var dx = to.X - from.X;
        var dz = to.Z - from.Z;
        return MathF.Sqrt((dx * dx) + (dz * dz));
    }

    internal static string WorldDirection(Vector3 from, Waypoint to)
    {
        var dx = to.X - from.X;
        var dz = to.Z - from.Z;

        if (MathF.Abs(dx) < 0.5f && MathF.Abs(dz) < 0.5f)
            return "到着";

        var horizontal = dx > 1.5f ? "東" : dx < -1.5f ? "西" : string.Empty;
        var vertical = dz > 1.5f ? "南" : dz < -1.5f ? "北" : string.Empty;

        return (vertical + horizontal) switch
        {
            "北東" => "↗ 北東",
            "南東" => "↘ 南東",
            "南西" => "↙ 南西",
            "北西" => "↖ 北西",
            "北" => "↑ 北",
            "東" => "→ 東",
            "南" => "↓ 南",
            "西" => "← 西",
            _ => "目的地付近",
        };
    }
}
