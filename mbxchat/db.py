import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from mbxchat import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS item (
    id     bigserial PRIMARY KEY,
    kind   text NOT NULL CHECK (kind IN ('grammar', 'sentence', 'word', 'term')),
    key    text NOT NULL,
    level  smallint,
    ko     text,
    en     text,
    data   jsonb NOT NULL DEFAULT '{}',
    UNIQUE (kind, key)
);
CREATE TABLE IF NOT EXISTS capture (
    id         bigserial PRIMARY KEY,
    text       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chunk (
    id            bigserial PRIMARY KEY,
    capture_id    bigint NOT NULL REFERENCES capture(id),
    ko            text NOT NULL,
    gloss         text NOT NULL,
    kind          text NOT NULL,
    register_note text NOT NULL,
    sentence      text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (capture_id, ko)
);
ALTER TABLE capture ADD COLUMN IF NOT EXISTS situation text NOT NULL DEFAULT '';
ALTER TABLE capture ADD COLUMN IF NOT EXISTS polite text;
ALTER TABLE capture ADD COLUMN IF NOT EXISTS casual text;
CREATE TABLE IF NOT EXISTS session (
    id         bigserial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_at    timestamptz NOT NULL DEFAULT now(),
    closed_at  timestamptz
);
CREATE TABLE IF NOT EXISTS prompt (
    id          bigserial PRIMARY KEY,
    session_id  bigint REFERENCES session(id),
    source      text NOT NULL CHECK (source IN ('capture', 'item')),
    ref         bigint NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('translate', 'grammar')),
    en          text NOT NULL,
    situation   text NOT NULL DEFAULT '',
    register    text NOT NULL DEFAULT '',
    reference   text,
    grammar_id  bigint,
    word        text,
    sent_at     timestamptz NOT NULL DEFAULT now(),
    answer      text,
    grade       jsonb,
    answered_at timestamptz,
    skipped     boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS drill (
    id           bigserial PRIMARY KEY,
    source       text NOT NULL CHECK (source IN ('capture', 'item')),
    ref          bigint NOT NULL,
    step         smallint NOT NULL DEFAULT 0,
    due          date NOT NULL,
    last_verdict text,
    times        integer NOT NULL DEFAULT 0,
    UNIQUE (source, ref)
);
CREATE TABLE IF NOT EXISTS setting (
    key   text PRIMARY KEY,
    value text NOT NULL
);
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS anki_note_id bigint;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS anki_error text;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS uid uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE capture ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'sentence';
CREATE TABLE IF NOT EXISTS word_card (
    id           bigserial PRIMARY KEY,
    capture_id   bigint NOT NULL UNIQUE REFERENCES capture(id),
    uid          uuid NOT NULL DEFAULT gen_random_uuid(),
    korean       text NOT NULL,
    english      text NOT NULL,
    dictionary   text NOT NULL,
    examples     jsonb NOT NULL,
    anki_note_id bigint,
    anki_error   text,
    duplicate    boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS krdict_cache (
    key     text PRIMARY KEY,
    body    text NOT NULL,
    created timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS known_grammar (
    item_id bigint PRIMARY KEY REFERENCES item(id) ON DELETE CASCADE,
    since   timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE prompt ADD COLUMN IF NOT EXISTS pick text NOT NULL DEFAULT 'new';
ALTER TABLE prompt ADD COLUMN IF NOT EXISTS focus text;
CREATE TABLE IF NOT EXISTS mistake (
    id         bigserial PRIMARY KEY,
    prompt_id  bigint NOT NULL REFERENCES prompt(id),
    category   text NOT NULL CHECK (category IN ('particle', 'ending', 'spelling', 'spacing', 'other')),
    wrong      text NOT NULL,
    fix        text NOT NULL,
    grammar_id bigint,
    created_at timestamptz NOT NULL DEFAULT now()
);
"""


def init(url: str | None = None) -> None:
    with psycopg.connect(url or config.DATABASE_URL, autocommit=True, row_factory=dict_row) as conn:
        conn.execute(SCHEMA)
        PostgresSaver(conn).setup()


def checkpointer(url: str | None = None) -> PostgresSaver:
    """LangGraph's checkpointer on a small pool; the pool replaces connections that died."""
    pool = ConnectionPool(
        url or config.DATABASE_URL, max_size=4, open=True, check=ConnectionPool.check_connection,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    return PostgresSaver(pool)
