import pytest

import app as app_module


class FakeCache:
    """In-memory replacement for Redis, used only in unit tests."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = str(value)
        self.ttls[key] = ttl


@pytest.fixture
def client(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(app_module, "cache", fake)
    monkeypatch.setattr(app_module.time, "sleep", lambda seconds: None)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), fake


def test_health(client):
    c, _ = client
    response = c.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_fibonacci_values():
    assert app_module.fibonacci(0) == 0
    assert app_module.fibonacci(1) == 1
    assert app_module.fibonacci(10) == 55
    assert app_module.fibonacci(30) == 832040


def test_compute_first_request_is_not_cached(client):
    c, _ = client
    data = c.get("/compute/10").get_json()
    assert data["result"] == 55
    assert data["cached"] is False


def test_compute_second_request_is_cached(client):
    c, _ = client
    c.get("/compute/10")
    data = c.get("/compute/10").get_json()
    assert data["result"] == 55
    assert data["cached"] is True


def test_compute_saves_result_with_60_second_ttl(client):
    c, fake = client
    c.get("/compute/10")
    assert fake.ttls["fib:10"] == 60
