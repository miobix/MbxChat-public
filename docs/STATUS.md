# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 2 (content import + `/grammar`) built and tested; PR open, the user merges after
`/grammar 는데` works on the phone. Next: unit 3 (capture as a fixed LangGraph workflow).

## Next
- **User:** try `/grammar 는데` and `/grammar 은/는` (→ `[↩ Not known]`) on the phone.
- **Unit 3:** capture workflow (draft → krdict → MbxRead usage → critic → chunks → interrupt),
  Pydantic outputs, Phoenix tracing.
- In BotFather, turn off "Allow Groups" (`/setjoingroups` → Disable) so the bot cannot be
  added to group chats.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- The daily bot runs in compose (`docker compose up -d --build`); `restart: unless-stopped`.
  Token and allowed user ID in `.env`. Missing either → the process exits with what's missing.
- `/` menu: set by the bot at startup for the allowed chat only (default scope cleared).
  Currently `help`, `grammar`, `demo`. `/demo` is a UI preview; remove it once real flows replace it.
- Free text → "Capture this?"; capturing itself is a stub until unit 3 (nothing saved).
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Compose: `bot` health on `127.0.0.1:8005`, `db` on `127.0.0.1:5434` (5432 and 5433 are taken).
  Tests need `docker compose up -d --wait db`. `.env` must exist (copy `.env.example`).
- Tests: 52 passing (`.venv/Scripts/python -m pytest tests -q`), Telegram fully mocked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `.venv/Scripts/python -m mbxchat.importer` on the host. Nothing reads
  MbxWrite (gone in production): files copied once, wishes imported once, and the Postgres
  volume is now their only copy. Provenance in `docs/DATA.md`.
  Known grammar points live in `known_grammar`; basics seeded on the first import only.
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
