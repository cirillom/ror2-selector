# RoR2 Eclipse Selector

`ror2-selector` is now a **Risk of Rain 2 BepInEx mod** instead of a separate web application.

The mod opens an in-game Eclipse roulette with **F7**. It reads the currently selected RoR2 profile, discovers survivors from the game's survivor catalog, reads their native Eclipse unlocks, and rolls a survivor for the next Eclipse run.

## Features

- In-game survivor roulette (`F7` by default)
- Uses the active Risk of Rain 2 profile — no separate users or SQLite database
- Reads native Eclipse progression rather than maintaining duplicate progress
- Can restrict rolls to unfinished Eclipse survivors
- Can restrict rolls to survivors unlocked on the current profile
- Automatically discovers current/DLC survivors through `SurvivorCatalog`
- Attempts to select the rolled survivor directly on the Eclipse screen
- Shows the current Eclipse level for every eligible survivor
- No R2API dependency for the initial version

In multiplayer, each player can run the mod and roll independently from their own profile. This replaces the old web app's party-profile system.

## Requirements

- Risk of Rain 2
- BepInExPack 5.4.2122 or newer compatible release
- .NET SDK for local development

## Build

The project references the assemblies from your installed copy of Risk of Rain 2.

PowerShell:

```powershell
$env:ROR2_DIR = "C:\Program Files (x86)\Steam\steamapps\common\Risk of Rain 2"
dotnet build -c Release
```

Nushell:

```nu
$env.ROR2_DIR = 'C:\Program Files (x86)\Steam\steamapps\common\Risk of Rain 2'
dotnet build -c Release
```

If your Steam library uses the default path, setting `ROR2_DIR` is optional.

The output DLL is:

```text
bin/Release/netstandard2.1/Ror2Selector.dll
```

## Install locally

Copy the built DLL to a folder inside:

```text
Risk of Rain 2/BepInEx/plugins/Ror2Selector/
```

Then launch the game through your modded profile and press **F7**.

## Eclipse progress

Risk of Rain 2 stores Eclipse progression as profile unlockables such as `Eclipse.Commando.2`. The mod asks the game's `EclipseRun.GetEclipseBaseUnlockableString` API for the correct survivor prefix at runtime and only falls back to known vanilla identifiers when necessary.

This means the mod does **not** modify or separately persist Eclipse progress. Winning an Eclipse run remains entirely handled by Risk of Rain 2.

## Thunderstore

`manifest.json` contains the package metadata and current BepInEx dependency. A release package should contain:

```text
manifest.json
README.md
CHANGELOG.md
icon.png
BepInEx/plugins/Ror2Selector/Ror2Selector.dll
```

## Previous web app

The old FastAPI/SQLite/Docker implementation remains available in Git history. Version `2.x` is the in-game mod rewrite.
