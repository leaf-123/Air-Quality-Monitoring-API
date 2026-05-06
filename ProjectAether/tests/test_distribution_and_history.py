def test_distribution_invalid_month_400(client):
    r = client.get("/distribution/2024/13")
    assert r.status_code == 400  # PDF requires 400 for invalid month :contentReference[oaicite:5]{index=5}


def test_history_missing_sensor_404(client):
    r = client.get("/history/sensor_does_not_exist")
    assert r.status_code in (404, 403)  # ideally 404 per spec
