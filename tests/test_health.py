import json
import urllib.error
import urllib.request

import pytest


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e) if e.headers.get("Content-Type") == "application/json" else None


def test_health_ok_with_database(db_url, health_url):
    assert _get(f"{health_url}/health") == (200, {"status": "ok"})


def test_health_503_without_database(health_url):
    assert _get(f"{health_url}/health") == (503, {"status": "db unavailable"})


@pytest.mark.parametrize("path", ["/", "/healthz", "/health/x"])
def test_unknown_paths_404(health_url, path):
    assert _get(f"{health_url}{path}")[0] == 404
