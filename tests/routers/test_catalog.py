from unittest.mock import patch


EMPTY_CATALOG = {
    "active_batch_id": None,
    "mentors": [],
    "curriculum": [],
    "classes": [],
    "packages": [],
}


def test_catalog_has_shared_cache_headers_and_etag(test_client):
    with patch("app.routers.catalog.crud_catalog.get_public_catalog", return_value=EMPTY_CATALOG):
        response = test_client.get("/catalog")

    assert response.status_code == 200
    assert "s-maxage=300" in response.headers["cache-control"]
    assert response.headers["surrogate-key"] == "public-catalog"
    assert response.headers["etag"]


def test_catalog_supports_conditional_request(test_client):
    with patch("app.routers.catalog.crud_catalog.get_public_catalog", return_value=EMPTY_CATALOG):
        first = test_client.get("/catalog")
        second = test_client.get("/catalog", headers={"If-None-Match": first.headers["etag"]})

    assert second.status_code == 304
    assert second.content == b""


def test_catalog_accepts_weak_etag_in_conditional_request(test_client):
    with patch("app.routers.catalog.crud_catalog.get_public_catalog", return_value=EMPTY_CATALOG):
        first = test_client.get("/catalog")
        second = test_client.get(
            "/catalog", headers={"If-None-Match": f'W/{first.headers["etag"]}'}
        )

    assert second.status_code == 304
