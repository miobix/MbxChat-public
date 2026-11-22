# DECISIONS (append-only log: never rewrite, never compress)

## 2026-11-22 Scope and stack
- **Telegram bot, long polling:** the phone's chat app is the UI, nothing listens on a public port, and a chat gives practice a session shape.
- **LangGraph** for orchestration: `interrupt()` plus a Postgres checkpointer match the Approve/Edit/Skip flow. Alternatives considered: Strands, Pydantic AI, OpenAI Agents SDK, a hand-written loop.
- **CPU-only open models, no paid APIs.** A cost router (rules → small GEC model → local LLM) keeps the expensive tier rare. Models are configuration; an unscoped model is added as an eval experiment.
- **Arize Phoenix via OpenTelemetry** for traces and evals: one container, where a self-hosted Langfuse needs about six. Moving to Langfuse is an exporter change; datasets would not migrate. LangSmith skipped: traces would leave the machine.
- **Prometheus + Grafana**, kept to one dashboard and one alert.
- **Cards hold chunks, the bot drills sentences:** long sentences make poor Anki cards, and the bot can grade full sentences where Anki cannot. Provisional until used.
- **Build the fixed workflow first (unit 3), then the agent (unit 7)**, and compare them on the same eval: the agent has to earn its extra cost.
- **MbxRead is an optional tool** over `host.docker.internal`; the bot works without it.
- **Content imported wide and pruned later**; personal sources stay in the local database.

## 2026-11-22 Unit 0: scaffold
- **Hashed lock from the start:** `requirements*.in` compiled by pip-tools into `requirements*.txt` with `--generate-hashes`; the image and CI install with `--require-hashes`, so every transitive package is pinned and verified. uv would do the same faster; it is not installed here and pip-tools is enough. Compiled on Windows, so the lock includes `tzdata` and `colorama` (Windows-only markers dropped); both are harmless on Linux, and the Linux image build proves nothing is missing.
- **Only what unit 0 uses is installed** (psycopg; pytest for dev). LangGraph, python-telegram-bot and the rest arrive with the units that use them.
- **The app process is a stdlib health server** (`/health`, 200 or 503 by a `SELECT 1`), so compose and CI have something real to check before the bot exists. Unit 1 builds the bot around it.
- **Postgres image reuses MbxRead's pinned pgvector image** (Postgres 18): already vetted and pulled, and the vector extension is there if learner memory ever wants it. Actions reuse MbxRead's SHA pins (vetted 2026-11-18).
- **Ports:** health `127.0.0.1:8005`, db `127.0.0.1:5434`.
- **Verified:** 5 tests; image 133 MB, runs as uid 10001; compose healthy; health goes 503 when db stops and back to 200 when it returns, no traceback.

## 2026-11-22 Unit 1 design: commands and chat UI
- **English UI, Korean content; no persistent reply keyboard** (user): the `/` menu plus inline buttons keep the chat clean.
- **Free text outside a session is assumed to be a capture, confirmed with one tap** (user): fewer accidental captures for the cost of one button.
- **Buttons edit their own message in place** and callback data carries only a short key into Postgres: the chat reads as a record of outcomes, and Telegram's 64-byte callback limit never constrains a payload.
- **A live progress message** covers CPU latency and makes the router's tiers visible.
- **The `/` menu is scoped to the allowed chat**, so strangers see no commands; set from code so it cannot drift from the handlers.
- **Grammar explainer added (user):** `/grammar <form>` and a `[📖 Grammar]` button on practice prompts, served from the NIKL pool's refreshers with no model call. Basic points (level-1 particles to start, grown by `[✓ I know this]`) are never offered. Lands with content import (unit 2) and the practice loop (unit 5).
