import psycopg

from mbxchat import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS item (
    id     bigserial PRIMARY KEY,
    kind   text NOT NULL CHECK (kind IN ('grammar', 'sentence', 'word', 'wish', 'term')),
    key    text NOT NULL,
    level  smallint,
    ko     text,
    en     text,
    data   jsonb NOT NULL DEFAULT '{}',
    UNIQUE (kind, key)
);
CREATE TABLE IF NOT EXISTS known_grammar (
    item_id bigint PRIMARY KEY REFERENCES item(id) ON DELETE CASCADE,
    since   timestamptz NOT NULL DEFAULT now()
);
"""


def init(url: str | None = None) -> None:
    with psycopg.connect(url or config.DATABASE_URL) as conn:
        conn.execute(SCHEMA)
