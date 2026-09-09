using RoR2;
using System;
using System.Linq;
using System.Reflection;

namespace Ror2Selector;

internal readonly struct EclipseProgress
{
    public EclipseProgress(int highestPlayableLevel, bool completed)
    {
        HighestPlayableLevel = highestPlayableLevel;
        Completed = completed;
    }

    public int HighestPlayableLevel { get; }
    public bool Completed { get; }

    public static EclipseProgress Read(UserProfile profile, SurvivorDef survivor)
    {
        var baseUnlockable = ResolveBaseUnlockable(survivor);
        if (string.IsNullOrWhiteSpace(baseUnlockable))
            return new EclipseProgress(1, false);

        var highest = 1;
        for (var level = 2; level <= 8; level++)
        {
            if (!HasUnlock(profile, $"{baseUnlockable}.{level}"))
                break;

            highest = level;
        }

        var completed = HasUnlock(profile, $"{baseUnlockable}.9");
        return new EclipseProgress(highest, completed);
    }

    private static bool HasUnlock(UserProfile profile, string unlockableName)
    {
        var def = UnlockableCatalog.GetUnlockableDef(unlockableName);
        return def is not null && profile.HasUnlockable(def);
    }

    private static string? ResolveBaseUnlockable(SurvivorDef survivor)
    {
        try
        {
            var methods = typeof(EclipseRun)
                .GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                .Where(m => m.Name == "GetEclipseBaseUnlockableString" && m.ReturnType == typeof(string));

            foreach (var method in methods)
            {
                var parameters = method.GetParameters();
                if (parameters.Length != 1)
                    continue;

                object? argument = null;
                var parameterType = parameters[0].ParameterType;

                if (parameterType == typeof(SurvivorDef))
                    argument = survivor;
                else if (parameterType == typeof(SurvivorIndex))
                    argument = survivor.survivorIndex;
                else if (parameterType == typeof(int))
                    argument = (int)survivor.survivorIndex;
                else if (parameterType == typeof(string))
                    argument = survivor.cachedName;

                if (argument is null)
                    continue;

                if (method.Invoke(null, new[] { argument }) is string value && !string.IsNullOrWhiteSpace(value))
                    return value.TrimEnd('.');
            }
        }
        catch (Exception ex)
        {
            Plugin.Log.LogDebug($"Could not resolve Eclipse unlockable via game API: {ex.Message}");
        }

        // Vanilla fallback. DLC/current survivors should normally resolve through
        // the game's own API, so new official survivors do not need a hard-coded row.
        return survivor.cachedName switch
        {
            "Commando" => "Eclipse.Commando",
            "Huntress" => "Eclipse.Huntress",
            "Toolbot" => "Eclipse.Toolbot",
            "Engi" => "Eclipse.Engi",
            "Mage" => "Eclipse.Mage",
            "Merc" => "Eclipse.Merc",
            "Treebot" => "Eclipse.Treebot",
            "Loader" => "Eclipse.Loader",
            "Croco" => "Eclipse.Croco",
            "Captain" => "Eclipse.Captain",
            "Bandit2" => "Eclipse.Bandit2",
            "Railgunner" => "Eclipse.Railgunner",
            "VoidSurvivor" => "Eclipse.VoidSurvivor",
            _ => null
        };
    }
}
