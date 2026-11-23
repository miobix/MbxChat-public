"""Load the content pools into `item` (SPEC §5; provenance in docs/DATA.md).

Public pools ship in data/ and load at bot startup. MbxRead saved terms are personal and load
with `python -m mbxchat.importer` on the host. Each kind is replaced as a whole, so re-running
is idempotent.
"""
import csv
import json
import re
import urllib.request
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from mbxchat import config, db

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
Row = tuple[str, str, int | None, str | None, str | None, dict]

# Level-1 points marked known on the first import (SPEC §7b); buttons add and remove later.
BASICS = ("g001", "g002", "g003", "g005", "g006", "g007", "g010", "g011", "g013", "g014", "g015",
          "g016", "g019")

_HEADING = re.compile(r"^## (g\d{3}) (.+)$")
_PREFIXES = {"register: ": "register", "check: ": "check", "vs ": "contrast"}


def _tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_refreshers(data_dir: Path = DATA_DIR) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for md in sorted((data_dir / "refreshers").glob("L*.md")):
        current = None
        for line in md.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if m := _HEADING.match(line):
                if m[1] in entries:
                    raise ValueError(f"duplicate refresher {m[1]} in {md.name}")
                current = entries[m[1]] = {"title": m[2], "file": md.name, "explanation": "",
                                           "examples": [], "notes": []}
            elif current is None or not line:
                continue
            elif line.startswith("- "):
                current["examples"].append(line[2:])
            elif line.startswith("note: "):
                current["notes"].append(line.removeprefix("note: "))
            elif prefix := next((p for p in _PREFIXES if line.startswith(p)), None):
                current[_PREFIXES[prefix]] = line if prefix == "vs " else line.removeprefix(prefix)
            else:
                current["explanation"] = f"{current['explanation']} {line}".strip()
    return entries


def grammar_rows(data_dir: Path = DATA_DIR) -> list[Row]:
    refreshers = load_refreshers(data_dir)
    rows = []
    for r in _tsv(data_dir / "grammar.tsv"):
        ref = refreshers[r["id"]]
        data = {k: r[k] for k in ("nikl_no", "category", "form", "related", "sense")} | ref
        rows.append(("grammar", r["id"], int(r["level"]), ref["title"], None, data))
    return rows


def sentence_rows(data_dir: Path = DATA_DIR) -> list[Row]:
    return [("sentence", r["id"], int(path.stem[1:]), r["ko"], r["en"],
             {k: r[k] for k in ("grammar_id", "register", "glosses")})
            for path in sorted((data_dir / "translations").glob("L*.tsv")) for r in _tsv(path)]


def word_rows(data_dir: Path = DATA_DIR) -> list[Row]:
    return [("word", r["lemma"], None, r["lemma"], None,
             {"grade": r["grade"], "rank": int(r["rank"]) if r["rank"] else None})
            for r in _tsv(data_dir / "vocab_levels.tsv")]


def fetch_terms(base_url: str) -> list[dict]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/terms", timeout=10) as resp:
        return json.load(resp)


def term_rows(terms: list[dict]) -> list[Row]:
    return [("term", str(t["id"]), None, t["lemma"], t["translation"],
             {"sentence": t["sentence"], "status": t["status"]})
            for t in terms if t["status"] != "ignored"]


def replace(conn: psycopg.Connection, kind: str, rows: list[Row]) -> tuple[int, int]:
    """Upsert every row of one kind and delete the ones the source no longer has."""
    assert all(r[0] == kind for r in rows)
    with conn.transaction():
        conn.cursor().executemany(
            "INSERT INTO item (kind, key, level, ko, en, data) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (kind, key) DO UPDATE SET level = EXCLUDED.level, ko = EXCLUDED.ko, "
            "en = EXCLUDED.en, data = EXCLUDED.data",
            [(*r[:5], Jsonb(r[5])) for r in rows],
        )
        removed = conn.execute(
            "DELETE FROM item WHERE kind = %s AND NOT (key = ANY(%s))", (kind, [r[1] for r in rows])
        ).rowcount
    return len(rows), removed


def import_public(url: str | None = None, data_dir: Path = DATA_DIR) -> list[str]:
    with psycopg.connect(url or config.DATABASE_URL) as conn:
        first = not _has(conn, "grammar")
        report = [_line(kind, replace(conn, kind, load(data_dir)))
                  for kind, load in (("grammar", grammar_rows), ("sentence", sentence_rows),
                                     ("word", word_rows))]
        if first:  # later, known points are the user's call
            conn.execute(
                "INSERT INTO known_grammar (item_id) SELECT id FROM item "
                "WHERE kind = 'grammar' AND key = ANY(%s)", (list(BASICS),)
            )
    return report


def import_personal(url: str | None = None) -> list[str]:
    if not config.MBXREAD_URL:
        return ["term: skipped, MBXREAD_URL not set"]
    try:
        terms = fetch_terms(config.MBXREAD_URL)
    except (OSError, ValueError) as e:
        return [f"term: skipped, MbxRead unavailable ({e})"]
    rows = term_rows(terms)
    with psycopg.connect(url or config.DATABASE_URL) as conn:
        have = conn.execute("SELECT count(*) FROM item WHERE kind = 'term'").fetchone()[0]
        if have and len(rows) < have / 2:  # an empty or wrong MbxRead would wipe the pool
            return [f"term: refused, MbxRead sent {len(rows)} terms but {have} are stored; "
                    "check MBXREAD_URL points at the daily MbxRead"]
        return [_line("term", replace(conn, "term", rows))]


def _has(conn: psycopg.Connection, kind: str) -> bool:
    return conn.execute("SELECT EXISTS (SELECT 1 FROM item WHERE kind = %s)", (kind,)).fetchone()[0]


def _line(kind: str, counts: tuple[int, int]) -> str:
    return f"{kind}: {counts[0]} rows, {counts[1]} removed"


if __name__ == "__main__":
    db.init()
    print("\n".join(import_public() + import_personal()))
