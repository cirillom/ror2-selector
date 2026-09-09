using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using RoR2;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace Ror2Selector;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed class Plugin : BaseUnityPlugin
{
    public const string PluginGuid = "com.cirillom.ror2selector";
    public const string PluginName = "RoR2 Eclipse Selector";
    public const string PluginVersion = "2.0.0";

    internal static ManualLogSource Log = null!;

    private ConfigEntry<KeyboardShortcut> toggleKey = null!;
    private ConfigEntry<bool> unfinishedOnly = null!;
    private ConfigEntry<bool> unlockedOnly = null!;

    private Rect windowRect = new(40f, 80f, 430f, 520f);
    private Vector2 scroll;
    private bool windowOpen;
    private SurvivorDef? lastRoll;
    private string status = "Press Roll to choose a survivor.";

    private void Awake()
    {
        Log = Logger;
        toggleKey = Config.Bind("General", "Toggle key", new KeyboardShortcut(KeyCode.F7), "Open or close the Eclipse selector.");
        unfinishedOnly = Config.Bind("Selection", "Unfinished only", true, "Only roll survivors whose Eclipse 8 has not been completed.");
        unlockedOnly = Config.Bind("Selection", "Unlocked survivors only", true, "Exclude survivors that are not unlocked on the current RoR2 profile.");

        Logger.LogInfo($"{PluginName} {PluginVersion} loaded.");
    }

    private void Update()
    {
        if (toggleKey.Value.IsDown())
            windowOpen = !windowOpen;
    }

    private void OnGUI()
    {
        if (!windowOpen)
            return;

        windowRect = GUI.Window(GetInstanceID(), windowRect, DrawWindow, "Eclipse Selector");
    }

    private void DrawWindow(int id)
    {
        GUILayout.BeginVertical();
        GUILayout.Label("Uses your current Risk of Rain 2 profile and Eclipse unlocks.");

        var profile = LocalUserManager.GetFirstLocalUser()?.userProfile;
        if (profile is null)
        {
            GUILayout.Space(8f);
            GUILayout.Label("No local profile is available yet. Open this after reaching the main menu.");
            GUILayout.EndVertical();
            GUI.DragWindow();
            return;
        }

        unfinishedOnly.Value = GUILayout.Toggle(unfinishedOnly.Value, "Unfinished Eclipse only");
        unlockedOnly.Value = GUILayout.Toggle(unlockedOnly.Value, "Unlocked survivors only");

        GUILayout.Space(8f);
        if (GUILayout.Button("ROLL SURVIVOR", GUILayout.Height(38f)))
            Roll(profile);

        GUILayout.Space(6f);
        GUILayout.Label(status);

        if (lastRoll is not null)
        {
            var progress = EclipseProgress.Read(profile, lastRoll);
            GUILayout.Label($"Selected: {GetDisplayName(lastRoll)}");
            GUILayout.Label(progress.Completed ? "Eclipse 8 completed" : $"Next Eclipse: {progress.HighestPlayableLevel}");

            if (GUILayout.Button("Select in Eclipse screen"))
            {
                status = TrySelectInEclipseScreen(lastRoll)
                    ? $"Selected {GetDisplayName(lastRoll)} in the Eclipse screen."
                    : "Could not find a compatible Eclipse selection screen. The roll is still valid.";
            }
        }

        GUILayout.Space(10f);
        GUILayout.Label("Current profile");
        scroll = GUILayout.BeginScrollView(scroll, GUILayout.ExpandHeight(true));

        foreach (var survivor in GetCandidates(profile, applyUnfinishedFilter: false))
        {
            var progress = EclipseProgress.Read(profile, survivor);
            var suffix = progress.Completed ? "E8 ✓" : $"E{progress.HighestPlayableLevel}";
            GUILayout.Label($"{GetDisplayName(survivor)}  —  {suffix}");
        }

        GUILayout.EndScrollView();
        GUILayout.EndVertical();
        GUI.DragWindow(new Rect(0, 0, 10000, 24));
    }

    private void Roll(UserProfile profile)
    {
        var candidates = GetCandidates(profile, unfinishedOnly.Value).ToList();
        if (candidates.Count == 0)
        {
            lastRoll = null;
            status = "No survivors match the current filters.";
            return;
        }

        lastRoll = candidates[UnityEngine.Random.Range(0, candidates.Count)];
        var progress = EclipseProgress.Read(profile, lastRoll);
        status = progress.Completed
            ? $"Rolled {GetDisplayName(lastRoll)} (E8 complete)."
            : $"Rolled {GetDisplayName(lastRoll)} — play Eclipse {progress.HighestPlayableLevel}.";

        TrySelectInEclipseScreen(lastRoll);
    }

    private IEnumerable<SurvivorDef> GetCandidates(UserProfile profile, bool applyUnfinishedFilter)
    {
        foreach (var survivor in SurvivorCatalog.allSurvivorDefs)
        {
            if (survivor is null)
                continue;

            if (IsHidden(survivor))
                continue;

            if (unlockedOnly.Value && !IsUnlocked(profile, survivor))
                continue;

            var progress = EclipseProgress.Read(profile, survivor);
            if (applyUnfinishedFilter && progress.Completed)
                continue;

            yield return survivor;
        }
    }

    private static bool IsUnlocked(UserProfile profile, SurvivorDef survivor)
    {
        try
        {
            var member = typeof(SurvivorDef).GetField("unlockableDef", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var unlockable = member?.GetValue(survivor) as UnlockableDef;
            return unlockable is null || profile.HasUnlockable(unlockable);
        }
        catch
        {
            return true;
        }
    }

    private static bool IsHidden(SurvivorDef survivor)
    {
        try
        {
            var field = typeof(SurvivorDef).GetField("hidden", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            return field?.GetValue(survivor) is bool hidden && hidden;
        }
        catch
        {
            return false;
        }
    }

    private static string GetDisplayName(SurvivorDef survivor)
    {
        var localized = Language.GetString(survivor.displayNameToken);
        return string.IsNullOrWhiteSpace(localized) || localized == survivor.displayNameToken
            ? survivor.cachedName
            : localized;
    }

    private static bool TrySelectInEclipseScreen(SurvivorDef survivor)
    {
        try
        {
            foreach (var behaviour in FindObjectsOfType<MonoBehaviour>())
            {
                var type = behaviour.GetType();
                if (type.FullName != "RoR2.UI.EclipseRunScreenController")
                    continue;

                foreach (var method in type.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Where(m => m.Name == "SelectSurvivor"))
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

                    if (argument is null)
                        continue;

                    method.Invoke(behaviour, new[] { argument });
                    return true;
                }
            }
        }
        catch (Exception ex)
        {
            Log.LogDebug($"Could not auto-select survivor: {ex.Message}");
        }

        return false;
    }
}
