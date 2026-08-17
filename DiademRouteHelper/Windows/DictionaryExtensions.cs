using System.Collections.Generic;

namespace DiademRouteHelper.Windows;

internal static class DictionaryExtensions
{
    internal static TValue GetValueOrDefault<TKey, TValue>(this IReadOnlyDictionary<TKey, TValue> dictionary, TKey key)
        where TKey : notnull
    {
        return dictionary.TryGetValue(key, out var value) ? value : default!;
    }
}
