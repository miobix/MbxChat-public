# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** cycle 3 (units 9-11, SPEC §8). Unit 9 (monitoring) merged (PR #17). **Unit 10 (recorded
demo, SPEC §7h) merged (PR #18).** The
demo is built in CI; it deploys to Pages only once the repo is public (DECISIONS "2026-11-24
Unit 10: recorded demo").

**Next: unit 11 (go public), the last unit; it closes cycle 3:** history and content sweep
(`publish-sanitized-repo`), README + FEATURES, flip the repo public, set Settings → Pages →
Source to "GitHub Actions" and check the first deploy, link the demo; then the hardening pass and
doc roll-up.

**On hold until there is more real-use data (user):** grader and model work. Going public goes on.

**History sweep in progress:** plan in DECISIONS "Unit 11: public repo plan"; the clean copy is
verified locally before anything is pushed, and the push waits for the user's OK.

**Grader attempt done and stopped (2026-11-24):** a required-grammar check failed its bar and was
reverted; it's a known limitation now (DECISIONS "Unit 11: the one grader attempt"). **For the
user:** proofread g67-g84 at the end of `evals/grader_set.md` (`check: ok / fix / drop`); until
then they run only with `--with-pending`.

## Cycle 2 in one paragraph
Practice (unit 5) serves grammar and translate prompts, grades them with `gemma4:e4b` (chosen in
6b on a labeled set of 66, GPU), and resurfaces grammar points on a 3/10/30/90-day ladder.
Capture runs as a tool-calling agent (unit 7): words get a krdict card, sentences run the unit 3
chain. Unit 8 made practice varied (captures never prompted back, pool sentences used once, then
generated ones) and gave it a memory: mistakes are tagged by diffing each answer against its
correction, and a mistake repeated twice steers at most one prompt in three (🎯 line, `/weak`).

## Later
- **Revisit memory with more data (user):** thresholds (2 in 30 days, one in three steered),
  tagging quality (`other` share, the 습니다 → 어요 register case), and an agent choosing the next
  drill once there are a few hundred graded answers.
- **Long multi-clause sentences** (conditionals, counterfactuals) are what writing practice
  should push toward; a candidate for generated prompts once memory has data.
- **README note for unit 11:** MbxRead material is used when `MBXREAD_URL` is set and ignored
  when not; the author shares MbxRead's Ollama. CPU vs GPU numbers: DECISIONS 2026-11-24
  "Unit 7 wrap-up".
- **README for unit 11 must have a "Known problems" section** (user): each known weakness of the
  pipelines, and why it cannot or did not change now. From unit 10 so far: the capture agent
  sometimes runs out of steps (2 of 6 sentence captures in one recording run, 0 of 12 in the
  next); the grader is soft on missing required grammar (a fine sentence with a near-synonym form
  usually gets `minor`, sometimes `correct`, instead of `wrong`: 11 of 12 labeled items not `wrong`;
  a focused check call didn't help, DECISIONS "Unit 11: the one grader attempt") and passed a broken
  -(으)ㄹ 것 sentence and flags some correct answers (false alarms 2 of
  18 on the eval set); the grader's corrections can rewrite toward the reference (the override now
  drops the stale note, but the "Nearly" stays); capture's casual line is not always 반말 (4 of 12 in the pool recording kept 요, mostly where the situation is a client, customer or lead). Why not
  fixed: the grader prompt was retried twice and the eval said no (DECISIONS "Unit 10"); bigger
  models need hardware this host doesn't have (SPEC §6). Also a scope line: Telegram allows voice messages, but audio ingestion is not part of the project (SPEC §1). Each reason must be technical: what was tried, what the evidence showed, or which constraint blocks it. Add anything the unit 11 pass finds.
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix keeps the verdict `correct`. Spacing slips are now recorded in `mistake`.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **Hardening proposals, not done:** retention for checkpoints, Phoenix traces and
  `krdict_cache` (all small; revisit at the unit 11 hardening pass). Backups sit on the same disk as the database;
  copying them off the machine is the user's call.
- **Shutdown noise (found in unit 9, for the unit 11 hardening pass):** each bot stop logs a
  psycopg pool `PythonFinalizationError` and two "Task was destroyed but it is pending" lines
  (the `forever` loops). Harmless at exit; fix by cancelling the loops and closing the pool in a
  `post_stop` hook.
- **Skill proposal, on hold:** `capture-smoke` (scratch-DB traced capture).

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose (`restart: unless-stopped`): `bot` (health `127.0.0.1:8005`), `mcp` (tool server on
  the bot's image, compose network only, `mcp:8006/mcp`), `db` (`127.0.0.1:5434`, user and
  database `mbxchat`), `phoenix` (`127.0.0.1:6006`, auth off), `backup` (`pg_dump` every 24 h
  from container start to `./backups`, newest 14; restore in README). **Rebuild with plain
  `docker compose up -d --build`**: naming only `bot` leaves `mcp` on old code. Rebuilds leave
  dangling images: `docker image prune -f --filter label=com.docker.compose.project=mbxchat`.
- Monitoring (SPEC §7g): `prometheus` (`127.0.0.1:9090`, 30 days), `grafana` (`127.0.0.1:3005`,
  no login, dashboard provisioned from `monitoring/grafana/`), `alertmanager` (network only;
  `BotDown` to the allowed chat). Rule tests: `monitoring/alerts_test.yml` via `promtool` in CI.
- Demo (SPEC §7h): `demo/index.html` + `demo/conversations.json`; rerecord with `demo/record.py`
  (command in §7h) after any change to what the bot sends. Preview: `python -m http.server` in
  `demo/`, then `http://127.0.0.1:8000/#0`…`#3`.
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
- krdict: `krdict_cache` table, `krdict_last` / `krdict_blocked_until` in `setting`.
- Lockfiles: use the `lockfile-recompile` skill (keeps the `pywin32` Windows marker).
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals: on the host (`requirements-eval.txt`, `PYTHONUTF8=1` when output goes to a file):
  `evals.grader_eval`, `evals.capture_side_by_side`, `evals.tool_calling`; needing `mcp`: the
  `eval-in-container` skill (`evals.capture_ab`). Results in `evals/results/`.
- Tests: 151 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model, krdict HTTP and MbxRead faked.
- Content: one `item` table (kinds grammar, sentence, word, term). Public pools (`data/`) are
  upserted at every bot start; MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002
  .venv/Scripts/python -m mbxchat.importer` on the host (refuses an answer with under half the
  stored count). Nothing reads MbxWrite. Provenance in `docs/DATA.md`. Known grammar in
  `known_grammar`; basics seeded on the first import only.
