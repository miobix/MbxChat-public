# MbxChat

A Telegram bot for practising written Korean, built as a LangGraph agent over local open
models. **In development**; the plan and units are in [docs/SPEC.md](docs/SPEC.md).

Built in public: agent orchestration with tools, human-in-the-loop approval, an MCP tool
server, a cost router over CPU-only models, tracing and evals (Arize Phoenix), and monitoring
(Prometheus + Grafana).

## Run it

Needs Docker (Compose 2.18+).

```sh
cp .env.example .env          # compose requires the file; fill in the Telegram values from unit 1
docker compose up -d --build  # bot (health on 127.0.0.1:8005) + Postgres (127.0.0.1:5434)
curl http://127.0.0.1:8005/health
```

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
