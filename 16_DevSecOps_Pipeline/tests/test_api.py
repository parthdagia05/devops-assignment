import pytest

from app import main


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    main.store = main.NoteStore()
    return main.app.test_client()


def test_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "GET /health" in res.get_json()["endpoints"]


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_security_headers(client):
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


def test_create_and_list(client):
    res = client.post("/notes", json={"title": "Buy milk", "body": "2 litres"})
    assert res.status_code == 201
    assert res.get_json()["id"] == 1
    assert client.get("/notes").get_json() == [{"id": 1, "title": "Buy milk", "body": "2 litres"}]


def test_create_invalid(client):
    assert client.post("/notes", json={}).status_code == 400
    assert client.post("/notes", data="not json").status_code == 400


def test_get_and_delete(client):
    client.post("/notes", json={"title": "a"})
    assert client.get("/notes/1").get_json()["title"] == "a"
    assert client.delete("/notes/1").status_code == 204
    assert client.get("/notes/1").status_code == 404
    assert client.delete("/notes/1").status_code == 404
