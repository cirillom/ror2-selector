from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_seeded_progress_and_crud(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "test.sqlite3"))

    with TestClient(app) as client:
        users = client.get("/users").json()
        survivors = client.get("/survivors").json()

        assert {user["name"] for user in users} == {"Jogador 1", "Amigo"}
        assert len(survivors) == 18
        assert "Heretic" not in {survivor["name"] for survivor in survivors}
        assert "Drifter" in {survivor["name"] for survivor in survivors}
        assert all(
            survivor["image_url"].startswith("/assets/survivors/")
            for survivor in survivors
        )
        dlc_counts = {}
        for survivor in survivors:
            dlc_counts[survivor["dlc_name"]] = (
                dlc_counts.get(survivor["dlc_name"], 0) + 1
            )
        assert dlc_counts == {
            "Base Game": 11,
            "Survivors of the Void": 2,
            "Seekers of the Storm": 3,
            "Alloyed Collective": 2,
        }

        create_response = client.post("/users", json={"name": "Teste"})
        assert create_response.status_code == 201
        user_id = create_response.json()["id"]

        progress = client.get(f"/users/{user_id}/progress").json()
        assert len(progress["levels"]) == 18
        assert all(item["level"] == 1 for item in progress["levels"])
        assert all(item["completed"] is False for item in progress["levels"])

        eclipse = progress["levels"][0]
        update_response = client.patch(
            f"/eclipse-levels/{eclipse['eclipse_level_id']}",
            json={"level": 8, "completed": True},
        )
        assert update_response.status_code == 200
        assert update_response.json()["level"] == 8
        assert update_response.json()["completed"] is True

        reset_response = client.post(f"/users/{user_id}/reset")
        assert reset_response.status_code == 200
        assert all(item["level"] == 1 for item in reset_response.json()["levels"])

        assert client.delete(f"/users/{user_id}").status_code == 204
        assert client.get(f"/users/{user_id}").status_code == 404


def test_constraints_and_survivor_fanout(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "test.sqlite3"))

    with TestClient(app) as client:
        assert client.post("/users", json={"name": "Amigo"}).status_code == 409
        assert client.patch("/eclipse-levels/1", json={"level": 9}).status_code == 422
        assert (
            client.patch("/eclipse-levels/1", json={"completed": True}).status_code
            == 400
        )

        survivor_response = client.post(
            "/survivors",
            json={
                "name": "Test Survivor",
                "image_url": "https://example.com/survivor.png",
            },
        )
        assert survivor_response.status_code == 201
        survivor_id = survivor_response.json()["id"]

        levels = client.get(
            "/eclipse-levels", params={"survivor_id": survivor_id}
        ).json()
        assert len(levels) == 2

        assert client.delete(f"/survivors/{survivor_id}").status_code == 204
        assert client.get(f"/survivors/{survivor_id}").status_code == 404
