# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 0 merged (PR #1). Unit 1 in progress on branch `unit-1-bot`.

## Next
- **Unit 1:** command map and chat UI decided (SPEC §7a, §7b). Build: long polling, allowlist,
  `/start` `/help`, per-chat `/` menu, errors in chat, the UI building blocks with a demo each.
- In BotFather, turn off "Allow Groups" (`/setjoingroups` → Disable) so the bot cannot be
  added to group chats.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Bot token and allowed user ID are in `.env` (2026-11-22).
- Compose: `bot` health on `127.0.0.1:8005`, `db` on `127.0.0.1:5434` (5432 and 5433 are taken).
  Tests need `docker compose up -d --wait db`. `.env` must exist (copy `.env.example`).
- Tests: 5 passing (`.venv/Scripts/python -m pytest tests -q`).
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
