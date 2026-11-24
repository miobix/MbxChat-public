import asyncio
import urllib.request
from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_ollama import ChatOllama
from prometheus_client import REGISTRY
from telegram.request import HTTPXRequest

from mbxchat import metrics, practice
from tests.test_practice import BAD


def _value(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_endpoint_serves_prometheus_text(health_url):
    with urllib.request.urlopen(f"{health_url}/metrics", timeout=5) as r:
        assert r.status == 200
        assert r.headers["Content-Type"].startswith("text/plain")
        body = r.read().decode()
    assert 'mbxchat_grades_total{tier="reference"}' in body
    assert "mbxchat_last_poll_timestamp_seconds" in body


def test_grades_are_counted_per_tier(monkeypatch):
    p = {"kind": "translate", "en": "x", "situation": "", "register": "", "reference": "회의가 미뤄졌어요.", "word": None}
    monkeypatch.setattr(practice, "ask", lambda *a: BAD)
    ref, llm = _value("mbxchat_grades_total", tier="reference"), _value("mbxchat_grades_total", tier="llm")
    practice.grade(p, "회의가 미뤄졌어요")
    practice.grade(p, "회의 미뤄졌어요")
    practice.grade(p, "회의 미뤄요")
    assert _value("mbxchat_grades_total", tier="reference") == ref + 1
    assert _value("mbxchat_grades_total", tier="llm") == llm + 2


def test_a_completed_long_poll_stamps_the_gauge(monkeypatch):
    monkeypatch.setattr(HTTPXRequest, "do_request", AsyncMock(return_value=(200, b"{}")))
    metrics.LAST_POLL.set(0)
    assert asyncio.run(metrics.PollRequest().do_request("https://x/getUpdates", "POST")) == (200, b"{}")
    assert _value("mbxchat_last_poll_timestamp_seconds") > 1e9


def test_a_failed_long_poll_leaves_the_gauge(monkeypatch):
    monkeypatch.setattr(HTTPXRequest, "do_request", AsyncMock(side_effect=OSError("down")))
    metrics.LAST_POLL.set(0)
    with pytest.raises(OSError):
        asyncio.run(metrics.PollRequest().do_request("https://x/getUpdates", "POST"))
    assert _value("mbxchat_last_poll_timestamp_seconds") == 0


def test_model_calls_are_timed_by_model_name():
    assert ChatOllama(model="gemma4:e4b")._get_ls_params()["ls_model_name"] == "gemma4:e4b"
    llm = FakeListChatModel(responses=["ok"], callbacks=[metrics.MODEL], metadata={"ls_model_name": "fake"})
    before = _value("mbxchat_model_call_seconds_count", model="fake")
    llm.invoke("hi")
    assert _value("mbxchat_model_call_seconds_count", model="fake") == before + 1
