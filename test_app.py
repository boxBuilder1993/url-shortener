import json
import os
import re

import pytest

import app as app_module
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Provide a Flask test client with a temporary urls.json file."""
    tmp_file = tmp_path / "urls.json"
    monkeypatch.setattr(app_module, "URLS_FILE", str(tmp_file))
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ─── Test 1: Successful URL shortening returns 201 with expected keys ───────

def test_shorten_success_returns_201(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": "https://example.com"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "short_code" in data
    assert "short_url" in data


# ─── Test 2: short_code is 6 alphanumeric characters ────────────────────────

def test_short_code_is_6_alphanumeric(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": "https://example.com"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    code = resp.get_json()["short_code"]
    assert len(code) == 6
    assert re.fullmatch(r"[A-Za-z0-9]{6}", code), f"Code '{code}' is not 6 alphanumeric chars"


# ─── Test 3: Redirect on valid code returns 302 to original URL ─────────────

def test_redirect_valid_code(client):
    original_url = "https://www.google.com"
    shorten_resp = client.post(
        "/shorten",
        data=json.dumps({"url": original_url}),
        content_type="application/json",
    )
    assert shorten_resp.status_code == 201
    code = shorten_resp.get_json()["short_code"]

    redirect_resp = client.get(f"/{code}")
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["Location"] == original_url


# ─── Test 4: 404 for unknown code ────────────────────────────────────────────

def test_redirect_unknown_code_returns_404(client):
    resp = client.get("/unknownXYZ")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


# ─── Test 5: 400 for missing `url` field in request body ────────────────────

def test_shorten_missing_url_field_returns_400(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"link": "https://example.com"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


# ─── Test 6: 400 for empty string URL ────────────────────────────────────────

def test_shorten_empty_string_url_returns_400(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


# ─── Test 7: 400 for malformed URL (no scheme) ───────────────────────────────

def test_shorten_malformed_url_no_scheme_returns_400(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": "notaurl"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


# ─── Test 8: 400 for non-HTTP URL (ftp://) ───────────────────────────────────

def test_shorten_ftp_url_returns_400(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": "ftp://files.example.com/resource"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


# ─── Test 9: Duplicate URL → two different short codes, both work ────────────

def test_duplicate_url_gets_two_different_codes(client):
    url = "https://duplicate.example.com"
    resp1 = client.post(
        "/shorten",
        data=json.dumps({"url": url}),
        content_type="application/json",
    )
    resp2 = client.post(
        "/shorten",
        data=json.dumps({"url": url}),
        content_type="application/json",
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201

    code1 = resp1.get_json()["short_code"]
    code2 = resp2.get_json()["short_code"]
    assert code1 != code2, "Duplicate URLs should get different short codes"

    # Both codes should redirect to the original URL
    redir1 = client.get(f"/{code1}")
    redir2 = client.get(f"/{code2}")
    assert redir1.status_code == 302
    assert redir2.status_code == 302
    assert redir1.headers["Location"] == url
    assert redir2.headers["Location"] == url


# ─── Test 10: POST without JSON content type / empty body → 400 ─────────────

def test_shorten_no_json_body_returns_400(client):
    resp = client.post("/shorten")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_shorten_non_json_content_type_returns_400(client):
    resp = client.post(
        "/shorten",
        data="url=https://example.com",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


# ─── Test 11: Multiple URLs can be shortened independently ───────────────────

def test_multiple_urls_shortened_independently(client):
    urls = [
        "https://first.example.com",
        "https://second.example.com",
        "https://third.example.com",
    ]
    codes = []
    for url in urls:
        resp = client.post(
            "/shorten",
            data=json.dumps({"url": url}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        codes.append(resp.get_json()["short_code"])

    # All codes must be unique
    assert len(set(codes)) == len(codes), "Each URL should get a unique code"

    # Each code should redirect to its corresponding original URL
    for code, original in zip(codes, urls):
        redir = client.get(f"/{code}")
        assert redir.status_code == 302
        assert redir.headers["Location"] == original


# ─── Test 12: short_url in response contains the short_code ─────────────────

def test_short_url_contains_short_code(client):
    resp = client.post(
        "/shorten",
        data=json.dumps({"url": "https://example.com/path?q=1"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["short_code"] in data["short_url"]
