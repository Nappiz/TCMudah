def test_request_observability_headers_are_always_present(test_client):
    response = test_client.get(
        "/healthz", headers={"X-Request-ID": "client-request-123"}
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "client-request-123"
    assert response.headers["x-db-queries"] == "0"
    assert "db;dur=" in response.headers["server-timing"]
    assert response.headers["x-instance-cold"] in {"0", "1"}


def test_latency_snapshot_is_available_to_admin(auth_client_admin):
    allowed = auth_client_admin.get("/admin/observability/latency")
    assert allowed.status_code == 200
    assert allowed.json()["scope"] == "current-instance"
    assert allowed.headers["cache-control"] == "no-store"


def test_latency_snapshot_is_admin_only(auth_client_user):
    denied = auth_client_user.get("/admin/observability/latency")
    assert denied.status_code == 403
