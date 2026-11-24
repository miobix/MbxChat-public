---
name: lockfile-recompile
description: Recompile all three MbxChat lockfiles (requirements.txt, requirements-dev.txt, requirements-eval.txt) after any change to a requirements*.in file, keep the pywin32 Windows marker, and check the diff for unexpected bumps. Use whenever a dependency is added, removed or bumped, or CI fails with ModuleNotFoundError for a package that works locally.
---

# lockfile-recompile

Three lockfiles, three consumers: `requirements.txt` → the image (Dockerfile); `requirements-dev.txt`
→ CI tests; `requirements-eval.txt` → host evals. The dev and eval files are constrained by
`requirements.txt` (`-c`), so they must be recompiled after it, every time. Unit 7 changed only
`requirements.txt`: CI went red with `No module named 'langchain_mcp_adapters'` while local tests
passed (the venv already had it).

## Steps (repo root, Git Bash)

1. Runtime first:
   `.venv/Scripts/pip-compile --allow-unsafe --generate-hashes --output-file=requirements.txt --strip-extras requirements.in -q`
2. **pywin32 marker:** on Windows, pip-compile pins `pywin32` (pulled by `mcp`) for every
   platform and the Linux image build fails. Make its line read
   `pywin32==<ver> ; sys_platform == "win32" \` (Edit tool). Check: `grep -n "^pywin32" requirements.txt`.
3. Then the two constrained files (they inherit the marker through `-c`):
   `.venv/Scripts/pip-compile --allow-unsafe --generate-hashes --output-file=requirements-dev.txt --strip-extras requirements-dev.in -q`
   `.venv/Scripts/pip-compile --allow-unsafe --generate-hashes --output-file=requirements-eval.txt --strip-extras requirements-eval.in -q`
4. **Read the diff:** `git diff --stat requirements*.txt` and `git diff requirements*.txt | grep "^[-+][a-z].*=="`.
   Only the packages you meant to change (and their new deps) should move. An unexpected bump:
   pin it in the `.in` file and rerun.
5. Verify: `.venv/Scripts/pip install --require-hashes -r requirements-dev.txt -q` and the test
   suite; `docker compose up -d --build` if `requirements.txt` changed (the image build is the real
   check of the marker). CI on the PR confirms the dev file.
