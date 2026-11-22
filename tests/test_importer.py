import sqlite3

import psycopg
import pytest

from mbxchat import config, importer


def _counts(url):
    with psycopg.connect(url) as conn:
        return dict(conn.execute("SELECT kind, count(*) FROM item GROUP BY kind").fetchall())


def _ids(url):
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT kind, key, id FROM item ORDER BY id").fetchall()


def test_every_grammar_point_has_a_complete_refresher():
    refreshers = importer.load_refreshers()
    for kind, key, level, title, _, data in importer.grammar_rows():
        ref = refreshers[key]
        assert ref["file"] == f"L{level}.md", key
        assert ref["register"] in ("both", "spoken", "written", "formal", "dated"), key
        assert 2 <= len(ref["examples"]) <= 3, key
        assert ref["explanation"], key
    assert len(refreshers) == 336


def test_public_counts_match_the_sources(db_url):
    report = importer.import_public()
    assert _counts(db_url) == {"grammar": 336, "sentence": 20, "word": 5543}
    assert report[0] == "grammar: 336 rows, 0 removed"
    with psycopg.connect(db_url) as conn:
        known = conn.execute("SELECT count(*) FROM known_grammar").fetchone()[0]
    assert known == len(importer.BASICS)


def test_reimport_is_idempotent(db_url):
    importer.import_public()
    before = _ids(db_url)
    importer.import_public()
    assert _ids(db_url) == before


def test_rows_gone_from_the_source_are_removed(db_url):
    with psycopg.connect(db_url) as conn:
        importer.replace(conn, "word", [("word", "가다", None, "가다", None, {}),
                                        ("word", "오다", None, "오다", None, {})])
        assert importer.replace(conn, "word", [("word", "가다", None, "가다", None, {})]) == (1, 1)
    assert _counts(db_url) == {"word": 1}


@pytest.fixture
def wish_db(tmp_path):
    path = tmp_path / "write.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE wish (id INTEGER PRIMARY KEY, english TEXT, situation TEXT, archived_at TEXT)")
        conn.executemany("INSERT INTO wish VALUES (?, ?, ?, ?)", [
            (1, "Seeded wish one", "at a café", None),
            (2, "Seeded wish two", "", None),
            (3, "Archived wish", "", "2026-01-01"),
        ])
    conn.close()
    return str(path)


TERMS = [
    {"id": 7, "lemma": "흐르다", "translation": "flow", "sentence": "강이 흐른다.", "status": "learning"},
    {"id": 8, "lemma": "가끔", "translation": "sometimes", "sentence": "", "status": "known"},
    {"id": 9, "lemma": "음", "translation": "um", "sentence": "", "status": "ignored"},
]


def test_personal_import_skips_archived_wishes_and_ignored_terms(db_url, wish_db, monkeypatch):
    monkeypatch.setattr(config, "MBXWRITE_DB", wish_db)
    monkeypatch.setattr(importer, "fetch_terms", lambda url: TERMS)
    assert importer.import_personal() == ["wish: 2 rows, 0 removed", "term: 2 rows, 0 removed"]
    assert _counts(db_url) == {"wish": 2, "term": 2}


def test_unavailable_sources_are_skipped_and_existing_rows_kept(db_url, monkeypatch):
    monkeypatch.setattr(importer, "fetch_terms", lambda url: TERMS)
    importer.import_personal()

    def down(url):
        raise OSError("connection refused")

    monkeypatch.setattr(importer, "fetch_terms", down)
    monkeypatch.setattr(config, "MBXWRITE_DB", "C:/no/such/write.db")
    report = importer.import_personal()
    assert report[0].startswith("wish: skipped, MbxWrite database unreadable")
    assert report[1] == "term: skipped, MbxRead unavailable (connection refused)"
    assert _counts(db_url) == {"term": 2}


def test_wishes_skipped_when_not_configured(db_url, monkeypatch):
    monkeypatch.setattr(config, "MBXWRITE_DB", "")
    monkeypatch.setattr(importer, "fetch_terms", lambda url: [])
    assert importer.import_personal()[0] == "wish: skipped (MBXWRITE_DB is not set)"
