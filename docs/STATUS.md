# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 1 (bot skeleton + UI kit) built and tested on the phone; PR open, the user
merges. Next: unit 2 (content import + `/grammar`).

## Next
- **Unit 2:** item schema, NIKL grammar pool + refreshers, translations, vocab, wishes and
  MbxRead terms (local only), `docs/DATA.md`, `/grammar <form>` with basics skipped (SPEC §7b).
  Bring back the template-database test fixture once tables exist.
- In BotFather, turn off "Allow Groups" (`/setjoingroups` → Disable) so the bot cannot be
  added to group chats.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- The daily bot runs in compose (`docker compose up -d --build`); `restart: unless-stopped`.
  Token and allowed user ID in `.env`. Missing either → the process exits with what's missing.
- `/` menu: set by the bot at startup for the allowed chat only (default scope cleared).
  Currently `help`, `demo`. `/demo` is a UI preview; remove it once real flows replace it.
- Free text → "Capture this?"; capturing itself is a stub until unit 3 (nothing saved).
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Compose: `bot` health on `127.0.0.1:8005`, `db` on `127.0.0.1:5434` (5432 and 5433 are taken).
  Tests need `docker compose up -d --wait db`. `.env` must exist (copy `.env.example`).
- Tests: 26 passing (`.venv/Scripts/python -m pytest tests -q`), Telegram fully mocked.
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
