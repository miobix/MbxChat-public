"""The MCP server end to end, in memory: the bot's LangChain adapter lists and calls its tools."""
import asyncio
import json

import psycopg
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.shared.memory import create_connected_server_and_client_session

from mbxchat import capture, config, importer, krdict, mcp_server

SEARCH = ("<channel><item><word>최적</word><pos>명사</pos><target_code>1</target_code><sense><translation>"
          "<trans_word>optimum</trans_word></translation></sense></item></channel>")


def _tool_names() -> set[str]:
    async def go():
        async with create_connected_server_and_client_session(mcp_server.build()._mcp_server) as session:
            return {t.name for t in await load_mcp_tools(session)}
    return asyncio.run(go())


def _call(name: str, args: dict):
    async def go():
        async with create_connected_server_and_client_session(mcp_server.build()._mcp_server) as session:
            tools = {t.name: t for t in await load_mcp_tools(session)}
            out = await tools[name].ainvoke(args)
            return json.loads(out if isinstance(out, str) else out[0]["text"])
    return asyncio.run(go())


def test_only_configured_tools_are_offered(db_url, monkeypatch):
    monkeypatch.setattr(config, "KRDICT_API_KEY", "")
    monkeypatch.setattr(config, "MBXREAD_URL", "")
    assert _tool_names() == {"known_items"}
    monkeypatch.setattr(config, "KRDICT_API_KEY", "k")
    monkeypatch.setattr(config, "MBXREAD_URL", "http://mbxread")
    assert _tool_names() == {"known_items", "krdict_lookup", "library_examples"}


def test_krdict_lookup_through_mcp(db_url, monkeypatch):
    monkeypatch.setattr(config, "KRDICT_API_KEY", "k")
    monkeypatch.setattr(krdict, "GAP", 0)
    monkeypatch.setattr(krdict, "_fetch", lambda url: SEARCH)
    assert _call("krdict_lookup", {"word": "최적"}) == {
        "available": True, "entries": [{"word": "최적", "pos": "명사", "target_code": "1", "glosses": ["optimum"]}]}


def test_a_paused_krdict_is_reported_not_raised(db_url, monkeypatch):
    monkeypatch.setattr(config, "KRDICT_API_KEY", "k")
    monkeypatch.setattr(krdict, "_fetch", lambda url: (_ for _ in ()).throw(OSError("down")))
    out = _call("krdict_lookup", {"word": "뷁"})
    assert out["available"] is False and "paused" in out["reason"]


def test_library_examples_through_mcp(db_url, monkeypatch):
    monkeypatch.setattr(config, "MBXREAD_URL", "http://mbxread")
    monkeypatch.setattr(capture, "_mbxread", lambda path, body: {"hits": [{"text": f"{body['lemma']} 예문."}]})
    assert _call("library_examples", {"lemma": "미루다"}) == {"available": True, "examples": ["미루다 예문."]}


def test_known_items_finds_terms_words_and_grammar(db_url):
    importer.import_public()
    with psycopg.connect(db_url) as conn:
        importer.replace(conn, "term", [("term", "미루다", None, "미루다", "put off", {"status": "learning"})])
    terms = _call("known_items", {"query": "미루다"})["matches"]
    assert {"kind": "term", "ko": "미루다", "en": "put off", "status": "learning", "known": False} in terms
    assert _call("known_items", {"query": "뷁뷁"}) == {"matches": []}
