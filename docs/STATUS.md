# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 6a (eval groundwork) merged. Unit 6b on `unit-6b-eval`, proofread done.

## Next
- **Grader set proofread** (2026-11-23): all 66 items `check: ok`; g51 verdict raised to wrong.
- **Shortlisted models pulled into MbxRead's Ollama** (2026-11-22; Q4_K_M where offered, else the
  smallest quant each repo has). Ollama digests (prefix): `hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M`
  `9f0107f24601` (4.4 GB), `hf.co/mykor/Midm-2.0-Mini-Instruct-gguf:Q4_K_M` `68bc4560da12`
  (1.4 GB), `hf.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF:UD-Q4_K_XL` `7988467f401f` (6.1 GB),
  `hf.co/OVHaiLLM/Olala-v1.0-mini-7A1B-GGUF:q5_k_m` `27bdade0292b` (6.0 GB),
  `hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M` `d31742299266` (3.4 GB); gemma4:e4b `dc35e8d9c606`.
  Move to DECISIONS when 6b records the eval; `ollama rm` the losers after it.
  Smoke test (2026-11-23, one correction prompt): A.X, Mi:dm, Nemotron, Qwen answer and fix it
  (Qwen needs `think: false`). **Olala dropped:** "unknown model architecture: 'olala'"; its
  model card says upstream llama.cpp and Ollama do not support it (OVHcloud fork only). Record
  in DECISIONS with 6b; `ollama rm` it then.
- **Unit 6b:** eval harness (runs in Phoenix), the five LLMs + dadeum on
  the set, side-by-side capture pass, reference-match + hints router, GPU attempt (SPEC §8).
  dadeum needs `torch` + `transformers`: keep them out of the bot image (eval-only deps).
- **Practice is shaped by use:** the user tweaks prompts, mix and grading as real use shows what
  to change; record each change in DECISIONS.
- **Model quality pass:** remember to compare grading and capture quality across different
  models, not only `gemma4:e4b` (unit 6 eval is the place).
- **End of cycle 2 (after unit 8):** run the two imported wishes through capture, then drop the
  `wish` kind (schema check, SPEC §5, importer notes). This app processes wishes at once; it
  does not store them.
- **Cycle 2 boundary:** after unit 8 merges, run the `hardening-pass` skill.
- **Hardening proposals, not done:** retention for LangGraph checkpoint tables and Phoenix
  traces (both tiny today; revisit at unit 9 monitoring). Backups sit on the same disk as the
  database; copying them off the machine is the user's call.
- **Skill proposal, on hold:** `capture-smoke` (`.claude/skills/`), scratch-DB traced capture.
  The user reconsiders it if the pattern repeats. Skills in use: CLAUDE.md, "Skills".
- Capture quality (critic wording, chunk choice, register slips like a polite draft without 요) is
  for the unit 6 eval, not prompt tweaks by feel.

## Facts
- Remote: `miobix/MbxChat`, private. Rulesets are not enforced on private repos on GitHub Free,
  so until unit 11 "never merge red" is a working rule. The user merges every PR on GitHub.
- Compose runs everything (`docker compose up -d --build`, `restart: unless-stopped`): `bot`
  (health `127.0.0.1:8005`), `db` (`127.0.0.1:5434`; 5432/5433 are taken), `phoenix`
  (`127.0.0.1:6006`, auth off, localhost only), `backup` (nightly `pg_dump` to `./backups`,
  newest 14; restore in README). Token and allowed user ID in `.env`; missing either → exit
  with what's missing.
- Practice (SPEC §7d): `/practice`, `/stop`, `/pause`; pings in `PRACTICE_TZ` (set in `.env`).
  Tables `session`, `prompt`, `drill`, `setting`.
- `/` menu: set at startup for the allowed chat only. `practice`, `stop`, `pause`, `help`,
  `grammar`, `queue`, `demo`. Groups
  disabled in BotFather. `/demo` is a UI preview; remove it once real flows replace it.
- Capture (SPEC §7c): ➕ runs draft → lookup → critic → chunks (~30-50 s on CPU), then one card
  per chunk; approved and edited chunks land in `chunk`. A pending ✏️ edit lives in memory (a
  restart forgets it). Needs MbxRead's stack: API :8002 (krdict via `/api/dict`, `/api/usage`)
  and its Ollama :11434 (`gemma4:e4b`, ID `dc35e8d9c606`, checked at startup with a warning).
- Anki (SPEC §7): deck `MbxChat`, note type `MbxChat Chunk` (created once; template changes in
  code do not reach an existing note type), AnkiConnect at `host.docker.internal:8765`. `chunk`
  is the outbox; retried every 60 s.
- Errors: reported in the chat, except Telegram network errors (logged; polling retries alone).
  `httpx` logging is held at WARNING because request URLs contain the token.
- Tests: 90 passing (`.venv/Scripts/python -m pytest tests -q`), need
  `docker compose up -d --wait db`; Telegram, Anki, model and MbxRead faked.
- Content: one `item` table. Public pools (`data/`) are upserted at every bot start; personal
  MbxRead terms via `.venv/Scripts/python -m mbxchat.importer` on the host (refuses an answer
  with under half the stored count). Nothing reads MbxWrite: its wishes were imported once and
  the database (and its backups) is their only copy. Provenance in `docs/DATA.md`. Known grammar
  in `known_grammar`; basics seeded on the first import only.
- MbxRead is reached at `host.docker.internal:8002`; its `.env` `ALLOWED_HOSTS` includes
  `host.docker.internal`.
