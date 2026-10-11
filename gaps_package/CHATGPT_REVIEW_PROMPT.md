# ChatGPT review prompt — copy everything below the line

---

You are reviewing a **gaps package** for Stephen’s skate rink project (`skate_pos`).

## Your job

1. Read the attached/pasted files: `KNOWN_BASELINE.md`, `GAPS_CATALOG.md`, `CONSTRAINTS.md`, `OPERATOR_NOTES.md`, `BOOTSTRAP_RETURN_SCHEMA.md`.
2. Treat the frozen UI rc.6 + Core 0.3.1-rc.1 as **read-only baseline**. Do not invent that checkout, NFC, or payments already exist.
3. Review whether the gap catalog is complete for a path to a **usable staff rental kiosk** with add/remove skates (manual + barcode/QR + NFC later) and a **payment processor or pay-by-QR** path.
4. Return a **helper bootstrap** that Cursor / a local coding agent can execute as bounded assignments — not a vague essay.

## Hard constraints

Obey `CONSTRAINTS.md`. Especially:
- No secrets in the reply  
- No “just edit the sealed Core zip”  
- No claiming UI freeze / release  
- Prefer ordered lanes and small assignment stubs with acceptance checks  

## Output format

Return **only** the document defined in `BOOTSTRAP_RETURN_SCHEMA.md`, titled:

`HELPER_BOOTSTRAP_RETURN_0001`

Include the optional JSON block if you can.

## Product goal (operator)

Stephen wants a rink rental kiosk/POS. Today he only has a local inventory companion. He needs a bootstrap that tells him **what to build first**, **what to ask vendors**, and **what to authorize next** in Cursor — not a rewrite of AoS philosophy.

Proceed.
