# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 4 (Anki) built on `unit-4-anki`; the unit 3 chunk already reached Anki live.
Awaiting the phone check: approve with Anki closed, open Anki, the card appears once.

## Next
- **Unit 4 phone check**, then PR. Unit 4 ends cycle 1: hardening pass (backups of the Postgres
  volume are on its list) and doc roll-up after the merge.
- **Skill proposal, on hold:** `capture-smoke` (`.claude/skills/`), scratch-DB traced capture.
  The user reconsiders it if the pattern repeats; unit 4 did not need it.
- Capture quality (critic wording, chunk choice, register slips like a polite draft without 요) is
  for the unit 6 eval, not prompt tweaks by feel.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- The daily bot runs in compose (`docker compose up -d --build`); `restart: unless-stopped`.
  Token and allowed user ID in `.env`. Missing either → the process exits with what's missing.
- `/` menu: set by the bot at startup for the allowed chat only (default scope cleared).
  Currently `help`, `grammar`, `queue`, `demo`. Groups are disabled in BotFather. `/demo` is a UI preview; remove it once real flows replace it.
- Capture (SPEC §7c): ➕ runs draft → lookup → critic → chunks (~30-50 s on CPU), then one card
  per chunk; approved and edited chunks land in `chunk`. A pending ✏️ edit lives in memory (a
  restart forgets it). Needs MbxRead's stack: API :8002 (krdict via `/api/dict`, `/api/usage`)
  and its Ollama :11434 (`gemma4:e4b`, ID `dc35e8d9c606`, checked at startup with a warning).
- Anki (SPEC §7): deck `MbxChat`, note type `MbxChat Chunk`, AnkiConnect on the desktop at
  `host.docker.internal:8765` from compose (already reachable). Queue retried every 60 s.
- Phoenix: `127.0.0.1:6006`, auth off (localhost only), SQLite in volume `mbxchat-phoenix`.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Compose: `bot` health on `127.0.0.1:8005`, `db` on `127.0.0.1:5434` (5432 and 5433 are taken).
  Tests need `docker compose up -d --wait db`. `.env` must exist (copy `.env.example`).
- Tests: 74 passing (`.venv/Scripts/python -m pytest tests -q`), Telegram fully mocked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `.venv/Scripts/python -m mbxchat.importer` on the host. Nothing reads
  MbxWrite (gone in production): files copied once, wishes imported once, and the Postgres
  volume is now their only copy. Provenance in `docs/DATA.md`. The term import refuses an
  answer with under half the stored count.
  Known grammar points live in `known_grammar`; basics seeded on the first import only.
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
