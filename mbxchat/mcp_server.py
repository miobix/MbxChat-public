"""MCP tool server (SPEC §4, §7e): read-only tools for the capture agent, over streamable HTTP.

Run as its own compose service: python -m mbxchat.mcp_server. A tool whose backend is not
configured (no krdict key, no MBXREAD_URL) is not offered at all.
"""
import psycopg
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row

from mbxchat import capture, config, krdict


def krdict_lookup(word: str) -> dict:
    """Look up a Korean word in its dictionary form (최적화, 미루다) in krdict, the national
    learners' dictionary. Returns up to 3 entries (homographs) with English glosses; an empty
    list means the word is not in this learners' dictionary (try its root: 최적화 → 최적)."""
    try:
        return {"available": True, "entries": krdict.search(word)}
    except krdict.Unavailable as e:
        return {"available": False, "reason": str(e)}


def library_examples(lemma: str, sentence: str = "") -> dict:
    """Real sentences using a Korean lemma, from the learner's reading library. `sentence` is
    the context to rank them by (defaults to the lemma)."""
    try:
        return {"available": True, "examples": capture.usage(lemma, sentence or lemma)}
    except capture.Unavailable as e:
        return {"available": False, "reason": str(e)}


def known_items(query: str) -> dict:
    """Whether a Korean word or grammar form is already among the learner's items: saved terms
    (with status), the graded vocabulary pool (grade A/B/C) and grammar points (known or not)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT kind, ko, en, level, data->>'status' AS status, data->>'grade' AS grade, "
            "EXISTS (SELECT 1 FROM known_grammar k WHERE k.item_id = item.id) AS known "
            "FROM item WHERE kind IN ('term', 'word', 'grammar') "
            "AND (ko = %(q)s OR key = %(q)s OR data->>'form' = %(q)s) ORDER BY kind LIMIT 5",
            {"q": query.strip()},
        ).fetchall()
    return {"matches": [{k: v for k, v in r.items() if v is not None} for r in rows]}


def build() -> FastMCP:
    server = FastMCP("mbxchat", host="0.0.0.0", port=config.MCP_PORT)
    server.tool()(known_items)
    if config.KRDICT_API_KEY:
        server.tool()(krdict_lookup)
    if config.MBXREAD_URL:
        server.tool()(library_examples)
    return server


if __name__ == "__main__":
    build().run(transport="streamable-http")
