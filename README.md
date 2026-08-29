# Risk of Rain 2 Eclipse Selector

Two-container Eclipse progress tracker and survivor roulette:

- `frontend`: static HTML/CSS/JavaScript served by BusyBox HTTPD
- `backend`: FastAPI CRUD API backed by SQLite

All public routing and TLS termination live in the single edge configuration at
`../edge/nginx/conf.d/ror2.cirillo.conf`. Neither application container has an
Nginx configuration.

The first startup seeds the 18 survivors from the original selector and the
profiles `Jogador 1` and `Amigo`. New users and survivors automatically receive
the corresponding Eclipse progress records.

The frontend bundles the 18 survivor portraits locally. Party mode accepts up
to four profiles and draws independently from each player's available or
lowest-Eclipse survivors, so the same survivor may be assigned more than once.
The DLC selector starts with all content enabled and filters the survivor grid,
progress total, solo roulette, and party roulette together.
The portrait files come from the corresponding file pages on the
[Risk of Rain 2 Wiki](https://riskofrain2.wiki.gg/wiki/Category:Survivors).

## Run

```bash
docker compose --env-file ../.env up -d --build
```

Open:

- Selector: `https://ror2.cirillo` or `https://ror2.lan.cirillo`
- Interactive API documentation: `https://ror2.cirillo/api/docs`
- API health check: `https://ror2.cirillo/api/health`

The homelab reverse-proxy vhost is stored at
`../edge/nginx/conf.d/ror2.cirillo.conf`. After starting the selector for the
first time, regenerate the SAN certificate and reload edge Nginx with:

```bash
sudo ../scripts/bin/regen-cert
```

Pi-hole already resolves both names through the existing wildcard rules.

Use the same `--env-file ../.env` option with other Compose commands.

## Configuration

To use a host bind mount instead of the managed Docker volume, place this
optional variable in the repository root `.env` file:

```dotenv
ROR2_DATA_DIR=/mnt/hdd/ror2-selector/data
```

Without `ROR2_DATA_DIR`, Compose stores SQLite in the managed `ror2-data` volume.
Both containers join the existing external `proxy` network and publish no host
ports; edge Nginx is their only public entry point.

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
```

The complete request and response schemas are available in Swagger UI at
`/api/docs` through edge Nginx.

## Backend tests

From `backend/`, install the development dependencies and run:

```bash
python -m pip install -r requirements-dev.txt
pytest
```
