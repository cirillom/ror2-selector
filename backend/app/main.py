from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status

from .database import Database
from .schemas import (
    EclipseLevelCreate,
    EclipseLevelRead,
    EclipseLevelUpdate,
    PartyWinRequest,
    ProgressEntry,
    SurvivorCreate,
    SurvivorRead,
    SurvivorUpdate,
    UserCreate,
    UserProgress,
    UserRead,
    UserUpdate,
)


def _database_path() -> str:
    return os.getenv("DATABASE_PATH", "/data/ror2-selector.sqlite3")


def _integrity_error(error: sqlite3.IntegrityError) -> HTTPException:
    message = str(error)
    if "UNIQUE constraint failed" in message:
        return HTTPException(status_code=409, detail="That record already exists")
    if "FOREIGN KEY constraint failed" in message:
        return HTTPException(status_code=404, detail="Referenced record not found")
    return HTTPException(status_code=400, detail="Database constraint failed")


def _row_or_404(row: sqlite3.Row | None, resource: str) -> sqlite3.Row:
    if row is None:
        raise HTTPException(status_code=404, detail=f"{resource} not found")
    return row


def _eclipse_from_row(row: sqlite3.Row) -> EclipseLevelRead:
    return EclipseLevelRead(
        id=row["id"],
        user_id=row["user_id"],
        survivor_id=row["survivor_id"],
        level=row["level"],
        completed=bool(row["completed"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDependency = Annotated[Database, Depends(get_database)]


def create_app(database_path: str | None = None) -> FastAPI:
    database = Database(database_path or _database_path())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        yield

    app = FastAPI(
        title="Risk of Rain 2 Eclipse Selector API",
        version="1.0.0",
        description="CRUD API for players, survivors, and Eclipse progress.",
        root_path=os.getenv("ROOT_PATH", ""),
        lifespan=lifespan,
    )
    app.state.database = database

    @app.get("/health", tags=["system"])
    def health(db: DatabaseDependency) -> dict[str, str]:
        with db.connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.get("/users", response_model=list[UserRead], tags=["users"])
    def list_users(db: DatabaseDependency) -> list[dict]:
        with db.connection() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    @app.post(
        "/users",
        response_model=UserRead,
        status_code=status.HTTP_201_CREATED,
        tags=["users"],
    )
    def create_user(payload: UserCreate, db: DatabaseDependency) -> dict:
        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO users (name) VALUES (?)", (payload.name,)
                )
                user_id = cursor.lastrowid
                connection.execute(
                    """
                    INSERT INTO eclipse_levels (user_id, survivor_id)
                    SELECT ?, id FROM survivors
                    """,
                    (user_id,),
                )
                row = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                return dict(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.get("/users/{user_id}", response_model=UserRead, tags=["users"])
    def get_user(user_id: int, db: DatabaseDependency) -> dict:
        with db.connection() as connection:
            row = _row_or_404(
                connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone(),
                "User",
            )
        return dict(row)

    @app.patch("/users/{user_id}", response_model=UserRead, tags=["users"])
    def update_user(
        user_id: int, payload: UserUpdate, db: DatabaseDependency
    ) -> dict:
        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    """
                    UPDATE users
                    SET name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (payload.name, user_id),
                )
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found")
                row = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                return dict(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.delete(
        "/users/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["users"],
    )
    def delete_user(user_id: int, db: DatabaseDependency) -> Response:
        with db.connection() as connection, connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/users/{user_id}/reset", response_model=UserProgress, tags=["users"])
    def reset_user(user_id: int, db: DatabaseDependency) -> UserProgress:
        with db.connection() as connection, connection:
            user = _row_or_404(
                connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone(),
                "User",
            )
            connection.execute(
                """
                UPDATE eclipse_levels
                SET level = 1, completed = 0, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            rows = _progress_rows(connection, user_id)
        return _progress_response(user, rows)

    @app.get(
        "/users/{user_id}/progress", response_model=UserProgress, tags=["users"]
    )
    def get_user_progress(user_id: int, db: DatabaseDependency) -> UserProgress:
        with db.connection() as connection:
            user = _row_or_404(
                connection.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone(),
                "User",
            )
            rows = _progress_rows(connection, user_id)
        return _progress_response(user, rows)

    @app.get(
        "/survivors", response_model=list[SurvivorRead], tags=["survivors"]
    )
    def list_survivors(db: DatabaseDependency) -> list[dict]:
        with db.connection() as connection:
            rows = connection.execute("SELECT * FROM survivors ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    @app.post(
        "/survivors",
        response_model=SurvivorRead,
        status_code=status.HTTP_201_CREATED,
        tags=["survivors"],
    )
    def create_survivor(
        payload: SurvivorCreate, db: DatabaseDependency
    ) -> dict:
        image_url = str(payload.image_url) if payload.image_url else ""
        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO survivors (name, image_url, dlc_name)
                    VALUES (?, ?, ?)
                    """,
                    (payload.name, image_url, payload.dlc_name),
                )
                survivor_id = cursor.lastrowid
                connection.execute(
                    """
                    INSERT INTO eclipse_levels (user_id, survivor_id)
                    SELECT id, ? FROM users
                    """,
                    (survivor_id,),
                )
                row = connection.execute(
                    "SELECT * FROM survivors WHERE id = ?", (survivor_id,)
                ).fetchone()
                return dict(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.get(
        "/survivors/{survivor_id}",
        response_model=SurvivorRead,
        tags=["survivors"],
    )
    def get_survivor(survivor_id: int, db: DatabaseDependency) -> dict:
        with db.connection() as connection:
            row = _row_or_404(
                connection.execute(
                    "SELECT * FROM survivors WHERE id = ?", (survivor_id,)
                ).fetchone(),
                "Survivor",
            )
        return dict(row)

    @app.patch(
        "/survivors/{survivor_id}",
        response_model=SurvivorRead,
        tags=["survivors"],
    )
    def update_survivor(
        survivor_id: int, payload: SurvivorUpdate, db: DatabaseDependency
    ) -> dict:
        fields: list[str] = []
        values: list[str | int] = []
        if "name" in payload.model_fields_set:
            fields.append("name = ?")
            values.append(payload.name or "")
        if "image_url" in payload.model_fields_set:
            fields.append("image_url = ?")
            values.append(str(payload.image_url) if payload.image_url else "")
        if "dlc_name" in payload.model_fields_set:
            fields.append("dlc_name = ?")
            values.append(payload.dlc_name or "Base Game")
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(survivor_id)

        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    f"UPDATE survivors SET {', '.join(fields)} WHERE id = ?", values
                )
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Survivor not found")
                row = connection.execute(
                    "SELECT * FROM survivors WHERE id = ?", (survivor_id,)
                ).fetchone()
                return dict(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.delete(
        "/survivors/{survivor_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["survivors"],
    )
    def delete_survivor(survivor_id: int, db: DatabaseDependency) -> Response:
        with db.connection() as connection, connection:
            cursor = connection.execute(
                "DELETE FROM survivors WHERE id = ?", (survivor_id,)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Survivor not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/eclipse-levels",
        response_model=list[EclipseLevelRead],
        tags=["eclipse levels"],
    )
    def list_eclipse_levels(
        db: DatabaseDependency,
        user_id: Annotated[int | None, Query(gt=0)] = None,
        survivor_id: Annotated[int | None, Query(gt=0)] = None,
    ) -> list[EclipseLevelRead]:
        conditions: list[str] = []
        values: list[int] = []
        if user_id is not None:
            conditions.append("user_id = ?")
            values.append(user_id)
        if survivor_id is not None:
            conditions.append("survivor_id = ?")
            values.append(survivor_id)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with db.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM eclipse_levels{where} ORDER BY user_id, survivor_id",
                values,
            ).fetchall()
        return [_eclipse_from_row(row) for row in rows]

    @app.post(
        "/eclipse-levels",
        response_model=EclipseLevelRead,
        status_code=status.HTTP_201_CREATED,
        tags=["eclipse levels"],
    )
    def create_eclipse_level(
        payload: EclipseLevelCreate, db: DatabaseDependency
    ) -> EclipseLevelRead:
        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO eclipse_levels
                        (user_id, survivor_id, level, completed)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        payload.user_id,
                        payload.survivor_id,
                        payload.level,
                        int(payload.completed),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM eclipse_levels WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            return _eclipse_from_row(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.post(
        "/eclipse-levels/party-win",
        response_model=list[EclipseLevelRead],
        tags=["eclipse levels"],
    )
    def record_party_win(
        payload: PartyWinRequest, db: DatabaseDependency
    ) -> list[EclipseLevelRead]:
        placeholders = ", ".join("?" for _ in payload.eclipse_level_ids)
        with db.connection() as connection, connection:
            rows = connection.execute(
                f"SELECT * FROM eclipse_levels WHERE id IN ({placeholders})",
                payload.eclipse_level_ids,
            ).fetchall()
            if len(rows) != len(payload.eclipse_level_ids):
                raise HTTPException(
                    status_code=404,
                    detail="One or more Eclipse levels were not found",
                )
            if len({row["user_id"] for row in rows}) != len(rows):
                raise HTTPException(
                    status_code=409,
                    detail="A party win can update each user only once",
                )

            connection.execute(
                f"""
                UPDATE eclipse_levels
                SET
                    level = CASE WHEN level < 8 THEN level + 1 ELSE level END,
                    completed = CASE WHEN level = 8 THEN 1 ELSE completed END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                payload.eclipse_level_ids,
            )
            updated_rows = connection.execute(
                f"SELECT * FROM eclipse_levels WHERE id IN ({placeholders})",
                payload.eclipse_level_ids,
            ).fetchall()

        by_id = {row["id"]: row for row in updated_rows}
        return [
            _eclipse_from_row(by_id[eclipse_level_id])
            for eclipse_level_id in payload.eclipse_level_ids
        ]

    @app.get(
        "/eclipse-levels/{eclipse_level_id}",
        response_model=EclipseLevelRead,
        tags=["eclipse levels"],
    )
    def get_eclipse_level(
        eclipse_level_id: int, db: DatabaseDependency
    ) -> EclipseLevelRead:
        with db.connection() as connection:
            row = _row_or_404(
                connection.execute(
                    "SELECT * FROM eclipse_levels WHERE id = ?",
                    (eclipse_level_id,),
                ).fetchone(),
                "Eclipse level",
            )
        return _eclipse_from_row(row)

    @app.patch(
        "/eclipse-levels/{eclipse_level_id}",
        response_model=EclipseLevelRead,
        tags=["eclipse levels"],
    )
    def update_eclipse_level(
        eclipse_level_id: int,
        payload: EclipseLevelUpdate,
        db: DatabaseDependency,
    ) -> EclipseLevelRead:
        fields: list[str] = []
        values: list[int] = []
        if "level" in payload.model_fields_set:
            fields.append("level = ?")
            values.append(payload.level or 1)
        if "completed" in payload.model_fields_set:
            fields.append("completed = ?")
            values.append(int(bool(payload.completed)))
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(eclipse_level_id)

        try:
            with db.connection() as connection, connection:
                cursor = connection.execute(
                    f"UPDATE eclipse_levels SET {', '.join(fields)} WHERE id = ?",
                    values,
                )
                if cursor.rowcount == 0:
                    raise HTTPException(
                        status_code=404, detail="Eclipse level not found"
                    )
                row = connection.execute(
                    "SELECT * FROM eclipse_levels WHERE id = ?", (eclipse_level_id,)
                ).fetchone()
            return _eclipse_from_row(row)
        except sqlite3.IntegrityError as error:
            raise _integrity_error(error) from error

    @app.delete(
        "/eclipse-levels/{eclipse_level_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["eclipse levels"],
    )
    def delete_eclipse_level(
        eclipse_level_id: int, db: DatabaseDependency
    ) -> Response:
        with db.connection() as connection, connection:
            cursor = connection.execute(
                "DELETE FROM eclipse_levels WHERE id = ?", (eclipse_level_id,)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Eclipse level not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


def _progress_rows(
    connection: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            eclipse_levels.id AS eclipse_level_id,
            survivors.id AS survivor_id,
            survivors.name AS survivor_name,
            survivors.image_url,
            survivors.dlc_name,
            eclipse_levels.level,
            eclipse_levels.completed
        FROM eclipse_levels
        JOIN survivors ON survivors.id = eclipse_levels.survivor_id
        WHERE eclipse_levels.user_id = ?
        ORDER BY survivors.id
        """,
        (user_id,),
    ).fetchall()


def _progress_response(
    user: sqlite3.Row, rows: list[sqlite3.Row]
) -> UserProgress:
    return UserProgress(
        user_id=user["id"],
        user_name=user["name"],
        levels=[
            ProgressEntry(
                eclipse_level_id=row["eclipse_level_id"],
                survivor_id=row["survivor_id"],
                survivor_name=row["survivor_name"],
                image_url=row["image_url"],
                dlc_name=row["dlc_name"],
                level=row["level"],
                completed=bool(row["completed"]),
            )
            for row in rows
        ],
    )


app = create_app()
