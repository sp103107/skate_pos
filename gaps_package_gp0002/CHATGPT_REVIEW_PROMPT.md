# ChatGPT review prompt — copy everything below the line

---

You are reviewing **gaps package GP-0002** for Stephen’s skate rink project (`skate_pos`).

## Context

GP-0001 produced Bootstrap v0.3.0. Cursor implemented **POS-A01** (Core successor asset model, staff session, demo/real workspace, migration, read-only Assets view). Status: CANDIDATE_COMPLETE, HANDOFF_ONLY.

Stephen launched the app and confirmed: **he still cannot add skates to inventory in the UI**. That enrollment surface was explicitly out of scope for A01 and belongs to **POS-A02**.

## Your job

1. Read: `KNOWN_BASELINE.md`, `OPERATOR_PAIN.md`, `GAPS_STATUS.md`, `CONSTRAINTS.md`, `BOOTSTRAP_RETURN_SCHEMA.md`.
2. Do **not** reinvent A01. Treat `register_asset` / r03 assets / staff session as landed.
3. Produce a **successor helper bootstrap** focused on the next usable steps, with **manual add/retire skates in the UI** as the immediate operator win.
4. Keep later rental/payment/NFC as ordered bounded assignments.

## Hard constraints

Obey `CONSTRAINTS.md`. Especially: no secrets; no editing sealed frozen zips; no fake payments; prefer copy-on-write successors; HANDOFF_ONLY; CANDIDATE_COMPLETE ≠ PASS.

## Output format

Return **only** the document defined in `BOOTSTRAP_RETURN_SCHEMA.md`, titled:

`HELPER_BOOTSTRAP_RETURN_0002`

Include the optional JSON block if you can.

## Product goal (operator)

Stephen needs to stock the rink counter from the UI, then move toward rental + pay-by-QR. Tell Cursor **exactly what to build next**, with acceptance checks he can see in the browser.

Proceed.
