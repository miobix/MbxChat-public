# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** all SPEC §8 units are done (cycles 1-3, units 0-11). The bot is in use; work
from here is shaped by that use. No unit is planned. New work starts as a SPEC change plus a
branch and PR on this repository.

**For the user, later:** proofread g67-g84 in `evals/grader_set.md`.

**On hold until there is more real-use data (user):** grader and model work.

## What the app is, in one paragraph
Capture (units 3, 7) runs as a tool-calling agent: words get a krdict card, sentences a chunked
correction, both to Anki through an outbox (unit 4). Practice (units 5, 8) serves grammar and
translate prompts, grades them with `gemma4:e4b` (chosen in 6b on a labeled set, GPU), resurfaces
grammar points on a 3/10/30/90-day ladder and steers one prompt in three to repeated mistakes.
Monitoring (unit 9) is Prometheus, Grafana and a `BotDown` alert; the recorded demo (unit 10) and
this public repository (unit 11) are the public face. Each step's reasons are in DECISIONS.

## Later
- **Revisit memory with more data (user):** thresholds (2 in 30 days, one in three steered),
  tagging quality (`other` share, the 습니다 → 어요 register case), and an agent choosing the next
  drill once there are a few hundred graded answers.
- **Long multi-clause sentences** (conditionals, counterfactuals) are what writing practice
  should push toward; a candidate for generated prompts once memory has data.
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix keeps the verdict `correct`. Spacing slips are now recorded in `mistake`.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **Retention, revisit at the next hardening pass:** none is needed yet (sizes in DECISIONS
  "Cycle 3 hardening pass"). Checkpoints grow about 17 kB per capture, the largest unbounded
  one. Backups sit on the same disk as the database; copying them off the machine is the
  user's call.
- **Idea for next cycle, unscoped (user): "how would a native reply to X".** Capture today is
  "how do I say this"; this is the reverse: paste what a Korean speaker said (plus optionally
  what the user replied) and get natural replies, as a post-conversation review ("I said A,
  what would have gone better?"). May be out of scope; decide at cycle planning.
- **Skill proposal, on hold:** `capture-smoke` (scratch-DB traced capture).
- **Spacing corrections feel like noise (user, from real use).** Look at real graded examples
  after the trailing-punctuation diff fix has been in use for a while: part of the noise may
  have been that display bug. Then decide: stricter, explained, or shown apart.
- **Screenshots:** `docs/img/` is taken with headless Chrome (commands in DECISIONS
  2026-11-25 "Real-use fixes"); retake after a demo page change.

## Facts
- Remote: `miobix/MbxChat-public`, public. The private `miobix/MbxChat` is a read-only archive
  (archived on GitHub; PRs #1-#19, commit map in `docs/PUBLIC_COPY.md`). Ruleset `main`: PR
  required, checks `test`, `demo`, `image` must pass, no force push or deletion. The user merges
  every PR on GitHub.
- Compose (`name: mbxchat`, `restart: unless-stopped`): `bot` (health `127.0.0.1:8005`), `mcp`
  (tool server on the bot's image, compose network only, `mcp:8006/mcp`), `db`
  (`127.0.0.1:5434`, user and database `mbxchat`), `phoenix` (`127.0.0.1:6006`, auth off),
  `backup` (`pg_dump` every 24 h from container start to `./backups`, newest 14; restore in
  README, proved in each hardening pass). **Rebuild with plain `docker compose up -d --build`**:
  naming only `bot` leaves `mcp` on old code. Rebuilds leave dangling images:
  `docker image prune -f --filter label=com.docker.compose.project=mbxchat`.
- Monitoring (SPEC §7g): `prometheus` (`127.0.0.1:9090`, 30 days), `grafana` (`127.0.0.1:3005`,
  no login, dashboard provisioned from `monitoring/grafana/`), `alertmanager` (network only;
  `BotDown` to the allowed chat). Rule tests: `monitoring/alerts_test.yml` via `promtool` in CI.
- Demo (SPEC §7h): `demo/index.html` + `demo/conversations.json`, live at
  https://miobix.github.io/MbxChat-public/; rerecord with the `record-demo` skill after any
  change to what the bot sends. Preview: `python -m http.server` in `demo/`, then
  `http://127.0.0.1:8000/#0`…`#3`.
- Config in `.env`: `KRDICT_API_KEY` (set), `MBXREAD_URL=http://host.docker.internal:8002`
  (set), `CAPTURE_MODE` (unset = agent), `ANKI_WORD_DECK` (unset = `MbxChat::Words`).
- Practice (SPEC §7d, §7f): `/practice`, `/stop`, `/pause`, `/weak`; pings in `PRACTICE_TZ`.
  Tables `session`, `prompt` (`pick` new/due/weak, `focus`), `drill` (grammar points; old
  capture and sentence rows ignored), `mistake`, `setting`. Free-text routing: SPEC §7e.
- `/` menu: set at startup for the allowed chat only. `/demo` is a UI preview; remove it once
  real flows replace it.
- Capture: workflow (SPEC §7c) and agent (SPEC §7e, default). A pending ✏️ edit lives in memory
  (a restart forgets it). Model `gemma4:e4b` (ID `dc35e8d9c606`, checked at startup) on
  MbxRead's Ollama :11434, GPU.
- Anki (SPEC §7): chunks → deck `MbxChat`, note type `MbxChat Chunk`; words →
  `ANKI_WORD_DECK`, note type `MbxChat Word` (template changes in code do not reach an existing
  note type). AnkiConnect at `host.docker.internal:8765`; both outboxes retried every 60 s.
- Shutdown: `post_stop` cancels the two background loops and `main` closes the checkpointer
  pool, so a stop logs nothing past "Application.stop() complete".
- krdict: `krdict_cache` table, `krdict_last` / `krdict_blocked_until` in `setting`.
- Lockfiles: use the `lockfile-recompile` skill (keeps the `pywin32` Windows marker).
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals: on the host (`requirements-eval.txt`, `PYTHONUTF8=1` when output goes to a file):
  `evals.grader_eval`, `evals.capture_side_by_side`, `evals.tool_calling`; needing `mcp`: the
  `eval-in-container` skill (`evals.capture_ab`). Results in `evals/results/`.
- Tests: 153 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model, krdict HTTP and MbxRead faked.
- Content: one `item` table (kinds grammar, sentence, word, term). Public pools (`data/`) are
  upserted at every bot start; MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002
  .venv/Scripts/python -m mbxchat.importer` on the host (refuses an answer with under half the
  stored count). Nothing reads MbxWrite. Provenance in `docs/DATA.md`. Known grammar in
  `known_grammar`; basics seeded on the first import only.
