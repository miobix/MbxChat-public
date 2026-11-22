import os
import threading
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from mbxchat import config, db

# Any database on this server works; tests create and drop their own.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://mbxchat:mbxchat@127.0.0.1:5434/postgres"
)


@pytest.fixture(autouse=True)
def _no_live_db(monkeypatch):
    """The default URL is the live database; a test that didn't ask for db_url must fail."""
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://nobody@127.0.0.1:9/none?connect_timeout=1")


@pytest.fixture(scope="session")
def _template_db():
    """The schema is built once; each test copies it with CREATE DATABASE ... TEMPLATE."""
    name = f"mbxchat_tmpl_{uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    db.init(make_conninfo(TEST_DATABASE_URL, dbname=name))
    yield name
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def db_url(monkeypatch, _template_db):
    name = f"mbxchat_test_{uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name} TEMPLATE {_template_db}")
    url = make_conninfo(TEST_DATABASE_URL, dbname=name)
    monkeypatch.setattr(config, "DATABASE_URL", url)
    yield url
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def health_url():
    from mbxchat.health import make_server

    server = make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
