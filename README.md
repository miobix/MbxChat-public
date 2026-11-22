# MbxChat

A Telegram bot for practising written Korean, built as a LangGraph agent over local open
models. **In development**; the plan and units are in [docs/SPEC.md](docs/SPEC.md).

Under the hood: agent orchestration with tools, human-in-the-loop approval, an MCP tool server,
a cost router over CPU-only models, tracing and evals (Arize Phoenix), and monitoring
(Prometheus + Grafana).

## Run it

Needs Docker (Compose 2.18+).

```sh
cp .env.example .env          # compose requires the file; fill in the Telegram values from unit 1
docker compose up -d --build  # bot (health on 127.0.0.1:8005) + Postgres (127.0.0.1:5434)
curl http://127.0.0.1:8005/health
```

Captures need MbxRead's compose stack running (its API on :8002 for krdict and library usage, its
Ollama on :11434 with `gemma4:e4b`). Traces: Phoenix at http://127.0.0.1:6006.

## Backups and moving machines

The `backup` service writes `mbxchat-<date>.dump` (`pg_dump -Fc`) daily into `BACKUP_DIR`
(default `./backups`, git-ignored) and keeps the newest 14 (`docker compose logs backup` shows
each run). The database holds data that exists nowhere else, so copy these off the machine.

To restore: clone, copy `.env`, then

```sh
docker compose up -d --wait db
docker compose exec -T db pg_restore -U mbxchat -d mbxchat --clean --if-exists < backups/mbxchat-<date>.dump
docker compose up -d --build
```

## Content

Public pools (NIKL grammar, refreshers, sentences, vocabulary) load at every bot start.
MbxRead saved terms are personal: imported on the host, kept in the local database only:

```sh
.venv/Scripts/python -m mbxchat.importer
```

Sources and licences: [docs/DATA.md](docs/DATA.md).

## Develop

Python 3.14. Dependencies are locked with hashes (`requirements*.txt`, compiled from
`requirements*.in` with pip-tools).

```sh
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-dev.txt
docker compose up -d --wait db
.venv/Scripts/python -m pytest tests -q
```

To add a dependency: edit the `.in` file, then
`pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements.txt requirements.in`
(and the same for `requirements-dev`).
