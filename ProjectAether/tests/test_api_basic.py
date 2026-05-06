def test_status_ok(client):
    r = client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "uptime_seconds" in data


def test_welcome_page_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_ingest_authorized_ok(client):
    payload = {"sensor_id": "sensor_amsterdam_001", "readings": {"pm25": 12.3}}
    r = client.post("/ingest", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("success", "ok", "healthy") or "message" in data


def test_ingest_unauthorized_403(client):
    payload = {"sensor_id": "sensor_unauthorized", "readings": {"pm25": 12.3}}
    r = client.post("/ingest", json=payload)
    assert r.status_code == 403  # PDF scenario: unauthorized must be 403 :contentReference[oaicite:3]{index=3}

def test_hydration_restores_latest_reading(tmp_path):
    storage = tmp_path / "readings.json"
    storage.write_text(
        '{"sensor_amsterdam_001":{"sensor_id":"sensor_amsterdam_001","timestamp":"2025-12-22T00:00:00+00:00","readings":{"pm25":10.0}}}'
    )

    from aether.sensor import SensorInfo
    from aether.sensor_manager import SensorManager

    s = SensorInfo(
        id="sensor_amsterdam_001",
        location="POINT(4.9 52.3)",
        latitude=52.3,
        longitude=4.9,
        metadata={},
    )

    mgr = SensorManager([s], str(storage))
    mgr.hydrate_from_storage()

    assert mgr.sensors["sensor_amsterdam_001"].last_reading.readings["pm25"] == 10.0
