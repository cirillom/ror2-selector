# Risk of Rain 2 Eclipse Selector

Single-container Eclipse progress tracker and survivor roulette. FastAPI serves
both the SQLite-backed API and the static HTML/CSS/JavaScript frontend from one
Docker image.

The first startup seeds the 18 official survivors and the profiles `Jogador 1`
and `Amigo`. New users and survivors automatically receive the corresponding
Eclipse progress records.

The frontend bundles all survivor portraits locally. Party mode accepts up to
four profiles and draws independently for each player, so the same survivor may
be assigned more than once. A party victory advances every assignment in one
database transaction. DLC filters apply to the grid, totals, and both roulette
modes.

## Develop

```bash
docker compose up --build
```

Open `http://localhost:8000`. Development data is stored in `./data-dev`,
which is ignored by Git. API documentation is available at
`http://localhost:8000/api/docs`.

Run the backend tests from the repository root with:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q backend/tests
```

## Release

Version tags trigger `.github/workflows/release.yml`. The workflow builds the
single image, publishes `latest` and the version tag to GHCR, and creates a
GitHub Release containing `docker-compose.example.yml`.

```bash
git tag v1.0.0
git push origin v1.0.0
```

Published images use `ghcr.io/cirillom/ror2-selector`.

## Deploy

The homeserver does not build application code. Copy
`docker-compose.example.yml` to
`/home/cirillo/services/ror2-selector/docker-compose.yml`, then run:

```bash
cd /home/cirillo/services/ror2-selector
docker compose pull
docker compose up -d
```

Persistent SQLite data lives in `/mnt/hdd/ror2-selector/data`. The container
joins the external `proxy` network and exposes port 8000 only to that network.
TLS and public routing remain the responsibility of the homeserver edge proxy.

## Data model

SQLite contains exactly three tables:

- `users`: player profiles
- `survivors`: playable survivor names, avatar URLs, and DLC names
- `eclipse_levels`: one row per user/survivor pair

`eclipse_levels.level` is constrained to `1` through `8`. The `completed` flag
represents winning Eclipse 8; this replaces the original HTML's implicit level
9 while preserving its progress calculation and completed-card behavior.

Deleting a user or survivor cascades to its progress records. Deleting an
individual progress record is supported by the CRUD API, but the web app uses
the automatically provisioned records.

## API routes

Each resource supports create, list, read, update, and delete operations:

```text
/api/users
/api/users/{user_id}
/api/survivors
/api/survivors/{survivor_id}
/api/eclipse-levels
/api/eclipse-levels/{eclipse_level_id}
```

Convenience endpoints used by the website:

```text
GET  /api/users/{user_id}/progress
POST /api/users/{user_id}/reset
POST /api/eclipse-levels/party-win
```

The party-win endpoint advances up to four assigned players in one transaction;
winning at Eclipse 8 marks that survivor as completed.

The complete request and response schemas are available in Swagger UI at
`/api/docs`.
