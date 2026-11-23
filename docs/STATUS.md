# STATUS (living state: rewrite in place, prune finished steps)

**Phase:** unit 6a (eval groundwork) merged. Unit 6b on `unit-6b-eval`: LLM and dadeum runs done, hints test next.

## Next
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
- **Unit 6b plan** (SPEC §8):
  1. Done: grader harness `evals/grader_eval.py` (one Phoenix experiment per model; per-item
     JSON in `evals/results/`; eval-only deps in `requirements-eval.txt`). `GRADER_MODEL` config.
  2. Done: all 5 LLMs on the set, CPU then GPU (`evals/results/grader_summary.jsonl`; the GPU
     lines carry `reference_hits`). GPU, of 66: gemma 43 verdicts / 2 false alarms / 52
     corrections / 1.4 s median; Nemotron 43/0/48/7.0 s; Mi:dm 37/1/38/0.8 s; Qwen 38/8/32/2.1 s
     (1 failure); A.X 35/9/36/1.6 s. Leading grader candidate: gemma.
  3. dadeum done: 0 false alarms, but it edits only 6 of the 48 answers with errors (missed 42);
     24 corrections right (18 of them unchanged correct answers); ~0.05 s per answer. Next: gemma
     with dadeum hints vs without. Run the harness with `PYTHONUTF8=1` when output goes to a file
     (Phoenix prints emoji; cp949 crashes).
  4. Router: reference match → correct with no call (done, tested). Live: 0 of 5 answers with a
     reference matched exactly; the set has 0 hits.
  5. Capture side-by-side: `evals/capture_side_by_side.py` ready, not run (needs MbxRead :8002).
  6. GPU: done. Ollama hit `cuInit failed: 500` ("named symbol not found"): Docker Desktop's
     packaged `libcuda.so.1` was older than the Windows driver (610.88). Updating Docker Desktop
     (4.99.0) fixed it; no compose change. gemma warm: 159-192 tok/s (CPU ~9). GPU rerun of all
     five models done (step 2). Record in DECISIONS with 6b.
  7. Pick grader + capture models, record in DECISIONS, `ollama rm` losers and Olala.
- **Later, not now (user):** move the benchmark core (grader set + harness + results log) into
  a standalone project, run once a month against new model versions. Spec it as its own project.
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
