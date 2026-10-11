# Skate POS — Gaps review package (GP-0001)

Upload this folder (or the zip beside it) to ChatGPT for review.  
Ask ChatGPT to return a **helper bootstrap** using the schema in `BOOTSTRAP_RETURN_SCHEMA.md`.

## Contents

| File | Purpose |
| --- | --- |
| `KNOWN_BASELINE.md` | What already exists (do not reinvent) |
| `GAPS_CATALOG.md` | Known gaps with IDs, priority, dependencies |
| `CONSTRAINTS.md` | Hard rules for any bootstrap advice |
| `CHATGPT_REVIEW_PROMPT.md` | Paste this as the main ChatGPT instruction |
| `BOOTSTRAP_RETURN_SCHEMA.md` | Exact structure ChatGPT must return |
| `OPERATOR_NOTES.md` | Stephen’s product intent in plain language |

## How to use with ChatGPT

1. Attach or paste the files in this package (at least `KNOWN_BASELINE.md`, `GAPS_CATALOG.md`, `CONSTRAINTS.md`, `BOOTSTRAP_RETURN_SCHEMA.md`).
2. Paste the full text of `CHATGPT_REVIEW_PROMPT.md` as your message.
3. Ask ChatGPT to reply with **only** the bootstrap package described in the schema (markdown + optional JSON block).
4. Save ChatGPT’s reply as `HELPER_BOOTSTRAP_RETURN_0001.md` (and `.json` if provided) and bring it back to Cursor / Foreman.

## Local / GitHub

- Package root: `M:\OTHER\test_rink_rental_app\skate_pos\gaps_package\`
- Zip (if present): `M:\OTHER\test_rink_rental_app\skate_pos\SKATE_POS_GAPS_PACKAGE_GP-0001.zip`
- Repo: https://github.com/sp103107/skate_pos
