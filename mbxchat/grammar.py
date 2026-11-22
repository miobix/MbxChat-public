"""Grammar explainer (SPEC §7b): loose form matching over the NIKL pool, rendered from refreshers."""
import re
from dataclasses import dataclass
from functools import cached_property

import psycopg

from mbxchat.ui import esc

_NOISE = re.compile(r"<[^>]*>|[-~\s\d]")
_OPTIONAL = re.compile(r"\([^)]*\)")


def variants(text: str) -> set[str]:
    """`-(으)면1` → {(으)면, 면, 으면}: hyphens, digits and spaces dropped; parentheses optional."""
    n = _NOISE.sub("", text)
    return {n, _OPTIONAL.sub("", n), n.replace("(", "").replace(")", "")} - {""}


@dataclass
class Point:
    id: int
    level: int
    title: str
    data: dict
    known: bool

    @cached_property
    def keys(self) -> set[str]:
        sources = [self.data["form"], *self.data["related"].split(","), self.title.split(" (")[0]]
        return set().union(*map(variants, sources))


def match(query: str, points: list[Point]) -> list[Point]:
    """Exact form first, then either side of a slash (은/는), then substring."""
    q = variants(query)
    parts = {p for v in q for p in v.split("/") if p}
    for hit in (lambda k: q & k, lambda k: parts & k, lambda k: any(v in key for v in q for key in k)):
        if found := [p for p in points if hit(p.keys)]:
            return found
    return []


_SELECT = (
    "SELECT i.id, i.level, i.ko, i.data, k.item_id IS NOT NULL FROM item i "
    "LEFT JOIN known_grammar k ON k.item_id = i.id WHERE i.kind = 'grammar'"
)


def load(url: str) -> list[Point]:
    with psycopg.connect(url) as conn:
        return [Point(*row) for row in conn.execute(_SELECT + " ORDER BY i.key")]


def get(url: str, item_id: int) -> Point | None:
    with psycopg.connect(url) as conn:
        row = conn.execute(_SELECT + " AND i.id = %s", (item_id,)).fetchone()
    return Point(*row) if row else None


def mark_known(url: str, item_id: int) -> None:
    with psycopg.connect(url) as conn:
        conn.execute("INSERT INTO known_grammar (item_id) VALUES (%s) ON CONFLICT DO NOTHING", (item_id,))


def explainer(p: Point) -> str:
    d = p.data
    lines = [f"📖 <b>{esc(p.title)}</b>  ·  level {p.level}  ·  {esc(d.get('register') or '?')}",
             esc(d["explanation"]),
             *(f"• {esc(e)}" for e in d["examples"])]
    if d.get("contrast"):
        lines.append(f"<i>{esc(d['contrast'])}</i>")
    lines += [f"<i>Note: {esc(n)}</i>" for n in d["notes"]]
    return "\n".join(lines)
