from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


DEFAULT_SURVIVORS = (
    ("Commando", "/assets/survivors/commando.png", "Base Game"),
    ("Huntress", "/assets/survivors/huntress.png", "Base Game"),
    ("Bandit", "/assets/survivors/bandit.png", "Base Game"),
    ("MUL-T", "/assets/survivors/mul-t.png", "Base Game"),
    ("Engineer", "/assets/survivors/engineer.png", "Base Game"),
    ("Artificer", "/assets/survivors/artificer.png", "Base Game"),
    ("Mercenary", "/assets/survivors/mercenary.png", "Base Game"),
    ("REX", "/assets/survivors/rex.png", "Base Game"),
    ("Loader", "/assets/survivors/loader.png", "Base Game"),
    ("Acrid", "/assets/survivors/acrid.png", "Base Game"),
    ("Captain", "/assets/survivors/captain.png", "Base Game"),
    (
        "Railgunner",
        "/assets/survivors/railgunner.png",
        "Survivors of the Void",
    ),
    (
        "Void Fiend",
        "/assets/survivors/void-fiend.png",
        "Survivors of the Void",
    ),
    ("Seeker", "/assets/survivors/seeker.png", "Seekers of the Storm"),
    ("Chef", "/assets/survivors/chef.png", "Seekers of the Storm"),
    (
        "False Son",
        "/assets/survivors/false-son.png",
        "Seekers of the Storm",
    ),
    ("Operator", "/assets/survivors/operator.png", "Alloyed Collective"),
    ("Drifter", "/assets/survivors/drifter.png", "Alloyed Collective"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(trim(name)) BETWEEN 1 AND 80),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS survivors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(trim(name)) BETWEEN 1 AND 80),
    image_url TEXT NOT NULL DEFAULT '',
    dlc_name TEXT NOT NULL DEFAULT 'Base Game'
        CHECK (length(trim(dlc_name)) BETWEEN 1 AND 80),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eclipse_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    survivor_id INTEGER NOT NULL REFERENCES survivors(id) ON DELETE CASCADE,
    level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 8),
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (completed = 0 OR level = 8),
    UNIQUE (user_id, survivor_id)
);

CREATE INDEX IF NOT EXISTS idx_eclipse_levels_user
    ON eclipse_levels(user_id);
CREATE INDEX IF NOT EXISTS idx_eclipse_levels_survivor
    ON eclipse_levels(survivor_id);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)
            self._migrate(connection)
            self._seed(connection)
            connection.commit()

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(survivors)").fetchall()
        }
        if "dlc_name" not in columns:
            connection.execute(
                """
                ALTER TABLE survivors
                ADD COLUMN dlc_name TEXT NOT NULL DEFAULT 'Base Game'
                """
            )

        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            survivor_count = connection.execute(
                "SELECT COUNT(*) FROM survivors"
            ).fetchone()[0]
            connection.execute("DELETE FROM survivors WHERE name = 'Heretic'")
            if survivor_count > 0:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO survivors (name, image_url, dlc_name)
                    VALUES (?, ?, ?)
                    """,
                    next(row for row in DEFAULT_SURVIVORS if row[0] == "Drifter"),
                )
            connection.execute("PRAGMA user_version = 1")

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        survivor_count = connection.execute(
            "SELECT COUNT(*) FROM survivors"
        ).fetchone()[0]
        if survivor_count == 0:
            connection.executemany(
                """
                INSERT INTO survivors (name, image_url, dlc_name)
                VALUES (?, ?, ?)
                """,
                DEFAULT_SURVIVORS,
            )
        else:
            connection.executemany(
                """
                UPDATE survivors
                SET
                    image_url = CASE
                        WHEN image_url LIKE 'https://api.dicebear.com/%' THEN ?
                        ELSE image_url
                    END,
                    dlc_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
                """,
                (
                    (image_url, dlc_name, name)
                    for name, image_url, dlc_name in DEFAULT_SURVIVORS
                ),
            )

        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            connection.executemany(
                "INSERT INTO users (name) VALUES (?)",
                (("Jogador 1",), ("Amigo",)),
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO eclipse_levels (user_id, survivor_id)
            SELECT users.id, survivors.id
            FROM users CROSS JOIN survivors
            """
        )
