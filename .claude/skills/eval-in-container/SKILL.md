---
name: eval-in-container
description: Run an MbxChat eval script inside a one-off container of the bot's image on the compose network, with evals/ mounted - for any eval that needs the mcp tool server (no host port) or the bot's exact runtime, e.g. evals/capture_ab.py. Use when an eval imports mbxchat.agent, calls MCP tools, or must match what the live bot runs; host-only evals (grader_eval, tool_calling) do not need it.
---

# eval-in-container

`evals/` is not in the image, and the `mcp` service has no host port, so evals that reach it run
in a throwaway container of the bot's image with `evals/` mounted.

## Steps

1. **Code first:** the container runs the image, not your working tree (only `evals/` is
   mounted). After any change under `mbxchat/`, rebuild every service:
   `docker compose up -d --build` (never `... bot` alone: `mcp` shares the image).
2. **Run**, from the repo root. The mount path must be absolute (a relative `./evals` came up
   empty under Git Bash):
   - Git Bash: `docker compose run --rm --no-deps -v "$(pwd -W)/evals:/app/evals" bot python -m evals.<script>`
   - PowerShell: `docker compose run --rm --no-deps -v "${PWD}/evals:/app/evals" bot python -m evals.<script>`

   `--no-deps` keeps compose from touching the running stack; the command override means no
   second Telegram poller starts. Long runs: background, output to a log in the scratchpad.
3. **Smoke the import first** when the script is new:
   `... bot python -c "import evals.<script>"` before a long run.
4. **Results** land in `evals/results/` on the host (the mount). Read them there.

## Rules the eval script must keep

- **No live rows:** call graph nodes directly (as `evals/capture_ab.py` does) rather than
  starting captures; captures feed practice and cards reach Anki.
- **krdict stays sparse:** the client paces and caches on its own; the script stops at the
  first "krdict unavailable" note and reports it (CLAUDE.md rule 3). A rerun of the same inputs
  is free (cached).
- A crash in report formatting must not lose a run: read optional fields with `.get()`.
