# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 7 (the agent) on `unit-7-agent`, 10 commits, not pushed. Steps 1-7 done; the
hybrid capture mode (7b) and the phone check (8) remain before the PR. Plan: SPEC §7e;
decisions: DECISIONS "2026-11-23 Unit 7 plan" and "2026-11-23 Unit 7 build".

**Next session starts with a plain recap of unit 7 for the user** (the summary below, a diagram of
bot / mcp / db / Ollama / krdict, and what each piece is for), before any new work.

## Unit 7 so far (2026-11-23)
1. **MbxRead is opt-in.** `MBXREAD_URL` empty by default: no MbxRead calls, no notes. The repo
   runs for anyone; the author's `.env` sets it.
2. **MbxChat's own krdict client** (`mbxchat/krdict.py`): every answer cached in Postgres, one
   request every 3 s, 30 min pause after the first failure. Gap and pause live in Postgres, so
   they hold across restarts and across the two processes that call krdict (bot, mcp).
3. **MCP tool server** (`mcp` compose service, the bot's image, `mbxchat/mcp_server.py`):
   read-only `krdict_lookup`, `library_examples` (only with `MBXREAD_URL`), `known_items`.
4. **Capture agent** (`mbxchat/agent.py`, behind `CAPTURE_MODE`, default `workflow`): decides
   word vs sentence; grounding stays fixed code (dictionary check, examples).
5. **Word capture → word cards:** "the word for optimization" → 최적화 (krdict misses it; root
   최적 found), examples that use the word (library full sentences, else krdict, else model,
   labelled), `[✅ Approve] [⏭ Skip]`, Anki deck `ANKI_WORD_DECK` (default `MbxChat::Words`),
   duplicate check against that deck. Word captures never come back as practice prompts.
6. **Session routing (live now, all modes):** Korean with a space = answer, graded, no extra
   call; a single Korean word = offered for capture; anything else = one quick classification,
   then `[➕ Capture] [💬 Answer it] [✍️ Grade it as my answer]`. Questions in English.
7. **Eval, workflow vs agent** (`evals/capture_ab.py`, `evals/results/capture_ab.md`): sentences
   3 model calls either way, agent used 0 tools and drafted flatter; words: agent 0.8 s with a
   real card, workflow just echoes the word. Bugs it found, fixed: tool calls written as text
   (4/10 agent sentence runs failed), word examples that did not contain the word.

## Left until the PR
- **7b. Hybrid (decided with the user, from the eval):** in agent mode a "sentence" decision
  drops the agent's draft and runs the workflow's `draft` node; words keep the agent path. Then
  rerun `evals/capture_ab.py` (cached, ~2 min) to confirm sentences match the workflow, and make
  `agent` the `CAPTURE_MODE` default. Small: one graph edge, tests, SPEC §7e.
- **8. Phone check (needs the user, ~10 min):** with `CAPTURE_MODE=agent` in `.env` and the bot
  rebuilt: capture "the word for optimization" → approve → the card shows in Anki (first real
  test of AnkiConnect's `"deck:…" "Korean:…"` duplicate query); capture a sentence; in a
  practice session send an English question, a single Korean word, and a Korean answer.
- **Then:** DECISIONS closing lines, `finish-unit` (tests, push, PR, CI). The user merges.
- **Needed from the user:** the phone check above. Optional: picks in `capture_ab.md`. Open,
  not blocking: the spacing-slips question below.

## Later
- **README note for unit 11:** MbxRead material is used when `MBXREAD_URL` is set and ignored
  when not; the author shares MbxRead's Ollama.
- **Open question (user): spacing slips.** `grade()` compares with spaces stripped, so a
  spacing-only fix (집에가서 → 집에 가서) keeps the verdict `correct`.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions.
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **End of cycle 2 (after unit 8):** run the two imported wishes through capture, then drop the
  `wish` kind (schema check, SPEC §5, importer notes); then the `hardening-pass` skill.
- **Hardening proposals, not done:** retention for LangGraph checkpoint tables, Phoenix traces
  and `krdict_cache` (all small; revisit at unit 9). Backups sit on the same disk as the
  database; copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (scratch-DB traced capture). Skills in use:
  CLAUDE.md, "Skills" (`eval-in-container` added 2026-11-23).

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose (`restart: unless-stopped`): `bot` (health `127.0.0.1:8005`), `mcp` (tool server on
  the bot's image, compose network only, `mcp:8006/mcp`), `db` (`127.0.0.1:5434`), `phoenix`
  (`127.0.0.1:6006`, auth off), `backup` (nightly `pg_dump` to `./backups`, newest 14; restore
  in README). **Rebuild with plain `docker compose up -d --build`**: naming only `bot` leaves
  `mcp` on old code. Token and allowed user ID in `.env`; missing either → exit with what's
  missing.
- Config in `.env`: `KRDICT_API_KEY` (set), `MBXREAD_URL=http://host.docker.internal:8002`
  (set; MbxRead's own `.env` `ALLOWED_HOSTS` includes `host.docker.internal`), `CAPTURE_MODE`
  (unset = workflow), `ANKI_WORD_DECK` (unset = `MbxChat::Words`).
- Practice (SPEC §7d): `/practice`, `/stop`, `/pause`; pings in `PRACTICE_TZ`. Tables `session`,
  `prompt`, `drill`, `setting`. Routing of free text in a session: SPEC §7e.
- `/` menu: set at startup for the allowed chat only. `practice`, `stop`, `pause`, `help`,
  `grammar`, `queue`, `demo`. Groups disabled in BotFather. `/demo` is a UI preview; remove it
  once real flows replace it.
- Capture: workflow (SPEC §7c) draft → lookup → critic → chunks (~3-6 s on GPU), one card per
  chunk into `chunk`; agent mode (SPEC §7e) adds the word path into `word_card`. A pending ✏️
  edit lives in memory (a restart forgets it). Model `gemma4:e4b` (ID `dc35e8d9c606`, checked at
  startup) on MbxRead's Ollama :11434, GPU; the only model kept after 6b.
- Anki (SPEC §7): chunks → deck `MbxChat`, note type `MbxChat Chunk`; words → `ANKI_WORD_DECK`,
  note type `MbxChat Word` (created once; template changes in code do not reach an existing
  note type). AnkiConnect at `host.docker.internal:8765`; both outboxes retried every 60 s.
- krdict: `krdict_cache` table, `krdict_last` / `krdict_blocked_until` in `setting`. Live use so
  far this unit: a handful of requests (최적화, 최적, 마감일, a few drafts' words).
- Lockfile: `pip-compile` on Windows pins `pywin32` (pulled by `mcp`) for every platform; re-add
  `; sys_platform == "win32"` to its line in `requirements.txt` or the image build fails.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Evals: on the host (`requirements-eval.txt`, `PYTHONUTF8=1` when output goes to a file):
  `python -m evals.grader_eval MODEL...`, `python -m evals.capture_side_by_side MODEL...`,
  `python -m evals.tool_calling MODEL...`. Needing the `mcp` service (no host port):
  `docker compose run --rm --no-deps -v "$(pwd -W)/evals:/app/evals" bot python -m evals.capture_ab`
  (Git Bash; a relative `-v ./evals` mount came up empty). Results in `evals/results/`.
- Tests: 135 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model, krdict HTTP and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `MBXREAD_URL=http://127.0.0.1:8002 .venv/Scripts/python -m mbxchat.importer`
  on the host (refuses an answer with under half the stored count). Nothing reads MbxWrite: its
  wishes were imported once and the database (and its backups) is their only copy. Provenance
  in `docs/DATA.md`. Known grammar in `known_grammar`; basics seeded on the first import only.
