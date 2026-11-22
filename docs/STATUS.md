# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 0 (scaffold) built on branch `unit-0-scaffold`; PR not opened yet.

## Next
- **Unit 0:** open the PR when the user says so; CI (`test`, `image`) must go green on it.
- **Start of unit 1: design talk on the command map** (commands, free text, buttons, and what
  the agent routes itself after unit 7); result goes into SPEC as a "Commands" section.
  The user wants a polished button UI, beyond a bot that takes numbers: cover inline keyboards
  edited in place, callback data design, the `/` menu and its scopes, formatting, and whether a
  Telegram Mini App earns a place.
- Before unit 1, the user creates the bot with Telegram's BotFather and puts the token and
  their user ID in `.env`.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free;
  add them when the repo goes public (unit 11).
- Compose: `bot` health on `127.0.0.1:8005`, `db` on `127.0.0.1:5434` (5432 and 5433 are taken).
  Tests need `docker compose up -d --wait db`. `.env` must exist (copy `.env.example`).
- Tests: 5 passing (`.venv/Scripts/python -m pytest tests -q`).
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
