# PEJIP ranking routine: instructions

The Claude Code routine on Babu's plan follows this file on every run
([design 0015](../design/0015-ranking-routine.md)). Its stored prompt is one line:

> Follow docs/routine/INSTRUCTIONS.md in this repository exactly.

Keeping the steps here, under version control, means a change to them is
reviewed like any other change and the routine always runs the current version.

## Rules

- Never commit, push, open a PR, or change any file in the repository. Never copy
  the queue, profile or answers into the repository.
- Never print `PEJIP_RANKING_KEY`, and never print the career profile or posting
  text in full. Report only counts and role ids.
- Work only in `/tmp/pejip-work`.

## Steps

1. From the repository root, install PEJIP in its own environment (it needs
   Python 3.12 or later):

   ```sh
   PY=$(command -v python3.13 || command -v python3.12 || command -v python3)
   "$PY" -m venv /tmp/pejip-venv && /tmp/pejip-venv/bin/pip install -q -e .
   ```

   Below, `R` means `/tmp/pejip-venv/bin/python -m pejip.routine --work /tmp/pejip-work`.
2. Run `R fetch`. If it reports 0 roles, say "No roles to rank" and stop. If it
   fails, report what it printed (never the key) and stop.
3. Run `R next`. It prints `STEP role <id> <feature>` with a `step.md` path,
   `REDO ...` with why the last answer was refused, or `DONE`. For STEP or REDO,
   read that `step.md` and follow it exactly (system prompt, input and JSON
   schema), write only the JSON answer to the file it names, and run `R next`
   again. You may hand each role to a helper agent that loops
   `R next --role <id>` until that role is DONE. If a role is refused 3 times in
   a row, run `R skip <id> "<short reason>"`.
4. When `R next` prints DONE, run `R submit --model "<the exact model id you are running on>"`.
5. End with one short summary: roles fetched, accepted, refused (ids and
   reasons), skipped, and errors.
