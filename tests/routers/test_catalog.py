from unittest.mock import patch


EMPTY_CATALOG = {
    "active_batch_id": None,
    "mentors": [],
    "curriculum": [],
    "classes": [],
    "packages": [],
}


def test_catalog_disables_all_http_caching(test_client):
    with patch("app.routers.catalog.crud_catalog.get_public_catalog", return_value=EMPTY_CATALOG):
        response = test_client.get("/catalog")

    assert response.status_code == 200
    assert response.headers["cache-control"] == (
        "no-store, no-cache, max-age=0, must-revalidate"
    )
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert "etag" not in response.headers
    assert "surrogate-key" not in response.headers


def test_catalog_ignores_conditional_cache_headers(test_client):
    with patch(
        "app.routers.catalog.crud_catalog.get_public_catalog",
        return_value=EMPTY_CATALOG,
    ) as get_catalog:
        first = test_client.get("/catalog")
        second = test_client.get(
            "/catalog", headers={"If-None-Match": '"old-catalog"'}
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == EMPTY_CATALOG
    assert get_catalog.call_count == 2
