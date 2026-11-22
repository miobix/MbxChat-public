# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** scope written (`SPEC.md`). Nothing built yet.

## Next
- **Unit 0, scaffold** (branch `unit-0-scaffold`): locked deps, compose with Postgres, ignore
  allowlists, `.env.example`, CI (tests + image build), pins.
- Before unit 1, the user creates the bot with Telegram's BotFather and puts the token and
  their user ID in `.env`.
- GitHub remote: private repo, created when the user says so.

## Facts
- Sibling project MbxRead is reached at `host.docker.internal:8002`; its `.env`
  `ALLOWED_HOSTS` already includes `host.docker.internal` (set 2026-11-22).
