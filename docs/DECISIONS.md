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

## 2026-11-22 Unit 1: bot skeleton and UI kit
- **python-telegram-bot 22.8** (June 2026, the newest release past the two-week rule). Alternatives: aiogram (async-first, router-based, popular in Russian-speaking communities), pyTelegramBotAPI (simpler, sync by default), raw Bot API over httpx. PTB has the largest docs and examples, a built-in JobQueue for the pings (unit 5) and typed objects for every Bot API feature used here (copy-text buttons, reactions, expandable quotes).
- **The allowlist is one `TypeHandler` in group -1** that raises `ApplicationHandlerStop` for anyone else, so no handler, present or future, can forget the check. Strangers get silence (no reply reveals that the bot is alive for someone).
- **The `/` menu is generated from the `COMMANDS` list** and set at startup: default scope cleared, the allowed chat scoped. The help text is built from the same list.
- **"Capture this?" quotes the user's message** (`do_quote`), and the callback reads the text back from `reply_to_message`. No callback payload and no state table are needed yet; the Postgres-backed key arrives when a button must carry data that is not on screen (unit 3).
- **Telegram network errors are logged, not sent to the chat:** polling already retries them, and a chat message during an outage would fail anyway. Everything else is reported in the chat.
- **`httpx` logging held at WARNING:** at INFO it logs every request URL, and Bot API URLs contain the token. Verified: the token does not appear in the container logs.
- **Pending updates are processed after a restart** (not dropped): a message sent while the bot was down still gets handled; Telegram keeps updates for 24 hours.
- **Tests mock Telegram entirely** (handlers called with `MagicMock`/`AsyncMock`, run with `asyncio.run`), so CI needs no token and no network; no pytest-asyncio dependency.
- **Verified:** 26 tests; compose healthy, survives a restart; menu empty in the default scope and `help`, `demo` in the allowed chat; every demo button checked on the phone by the user.

## 2026-11-22 Unit 2: content import and /grammar
- **Public pools copied into `data/`** (from MbxWrite `5ae386f`) rather than read from the MbxWrite install: the repo goes public, the image and CI need the files, and tests can check the counts. MbxChat now owns its copy; re-copy to sync.
- **One `item` table** (`kind`, `key`, `level`, `ko`, `en`, `data jsonb`, unique on kind + key) for grammar, sentences, words, wishes and terms. Practice (unit 5) draws from all of them, and their fields barely overlap, so the rest lives in `data`. Vocabulary grades A/B/C stay in `data`; they are not mapped onto levels 1-6.
- **Each kind is replaced as a whole** (upsert, then delete keys the source no longer has), in one transaction. Re-imports keep ids, and deletions at the source carry over. Revisit when practice history references items (unit 5): deleting a practised item may need to archive instead.
- **Public import runs at every bot start; personal import is a host command.** The container cannot see `write.db`, and personal data should move only when the user asks. A source that is not set or not reachable is skipped with a reason and its rows are kept.
- **Known grammar is its own table** (`known_grammar`), so re-imports never reset it. Seeded with 13 level-1 particles (이/가, 과/와, 까지, 은/는, 도, 을/를, 부터, 에, 에서, 의, 하고, 만, 보다), for the user to review; `[✓ I know this]` adds more.
- **`/grammar` matching is deterministic:** hyphens, digits and spaces dropped, parenthesised parts optional, the NIKL `related` column supplies the allomorphs. Exact match first, then either side of a slash, then substring. Two senses of one form (`-는데1`, `-는데2`) give a choice of buttons that edit the message in place.
- **DB calls from handlers are sync psycopg in `asyncio.to_thread`:** psycopg's async driver cannot run on Windows' default event loop, where the tests run, and one user does not need a pool.
- **Verified:** 52 tests; live counts match the sources (grammar 336, sentence 20, word 5543; wishes and terms match their sources, numbers kept out of the repo); a second import changes nothing; personal rows survive a bot restart.
- **MbxWrite is a one-time source (user):** its future is open, so the data files are a fork owned here (never re-synced) and wishes import once; later runs skip them. MbxRead terms still refresh on every run.
- **Known is reversible:** asking `/grammar` for a known point offers `[↩ Not known]`. Basics are seeded on the first import only, so an un-known basic stays un-known across restarts.
- **Nothing reads MbxWrite at run time (user, hardening):** MbxWrite will not exist in production. The wish importer, `MBXWRITE_DB` and their tests are removed after the one-time import; the `wish` kind stays in the schema for the imported rows. The Postgres volume is now the only copy of those wishes, which makes backups (hardening pass after unit 4) matter.

## 2026-11-22 Unit 3: capture as a fixed workflow
- **Ollama is MbxRead's compose service** (user): same `gemma4:e4b`, no second 6.6 GB copy, and our own CPU service would be no faster. It runs on CPU (not the GPU, as first assumed). If MbxRead is retired, MbxChat gets its own service; only `OLLAMA_URL` changes.
- **Thinking off** (`reasoning=False`): gemma4 spent ~900 hidden tokens and 70 s on a two-sentence draft; off, the same call takes ~5 s. A capture is ~30-50 s end to end.
- **krdict through MbxRead's `/api/dict`, not a client of our own:** MbxRead already caches lookups and stops all calls after one failure, and krdict has blocked this IP for bursts. One client per IP keeps that rule in one place; no second key, no XML parsing. MbxChat still spaces lookups 3 s apart. Cost: krdict is unavailable when MbxRead is down, which the workflow tolerates.
- **Library usage was already there** (MbxRead `POST /api/usage`, unit 5 of MbxRead), so no MbxRead change was needed (user chose "add an endpoint" before this was found).
- **krdict only for lemmas outside the NIKL pool** (user); usage for up to two lemmas outside the pool or graded B/C. Grade-A words gave useless usage hits (주, 회사).
- **One thread per capture**, not per chat: several captures can wait on buttons at once.
- **The bot drives the graph; the graph sends nothing.** Telegram messages are sent from the handler after each stream step and interrupt, so no node has a side effect that a resume could repeat. `review` holds one `interrupt()` per chunk and only collects decisions; `save` writes with `ON CONFLICT DO NOTHING`.
- **Sync LangGraph in worker threads** (`asyncio.to_thread(next, stream)`), same reason as unit 2: the async Postgres driver fails on Windows' default loop, where tests run. The checkpointer sits on a `psycopg_pool` pool so a dropped connection is replaced instead of poisoning every later capture.
- **Model output is cleaned in code where the model is unreliable:** shortened source sentences are mapped back to the full reviewed sentence, and critic entries without `→` are dropped (gemma sometimes returns `["casual", "polite"]`). Prompt quality is left to the unit 6 eval.
- **Phoenix 21.0.0, auth off:** it enables auth for any non-loopback bind, which a container always is; the port is published on 127.0.0.1 only, like the health endpoint.
- **Model pin:** Ollama pins by tag only, so the expected digest prefix (`dc35e8d9c606`) is config and checked at startup with a warning.
- **Term import guard** (from a side review during this unit): an answer with under half the stored terms is refused, so a wrong or empty MbxRead cannot wipe the pool.
- **Image 133 → 460 MB** (kiwipiepy model, numpy, gRPC for OTel). Accepted.
- **Verified:** 65 tests (real graph and Postgres checkpointer; model and MbxRead faked). Live, outside Telegram: three captures ran end to end (~28-50 s), the approved chunk was saved, and a traced run showed 19 spans in Phoenix covering every node and model call.
- **Phone check (user):** one real capture ended in an approved chunk; the trace shows all six nodes and three model calls. The wait is acceptable: the chat is asynchronous and chunks come one at a time, so the user does not sit and watch it.
