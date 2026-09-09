# Changelog

## 2.0.0

- Replace the FastAPI/SQLite/Docker web application with a native BepInEx Risk of Rain 2 mod.
- Add an F7 in-game Eclipse selector window.
- Read survivor data directly from `SurvivorCatalog`.
- Read Eclipse progression directly from the current RoR2 profile.
- Add unfinished-only and unlocked-only roulette filters.
- Attempt to auto-select the rolled survivor on the Eclipse screen.
- Remove the separate party/user database model; multiplayer players now use their own local RoR2 profiles.
