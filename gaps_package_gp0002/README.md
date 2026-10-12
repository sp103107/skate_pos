# SKATE_POS gaps review package GP-0002

Post–POS-A01 review package for ChatGPT. Successor to GP-0001 / Bootstrap v0.3.0.

## Why this exists

Stephen can run the A01 app and see inventory/assets, but **still cannot add skates in the UI**. That is expected: A01 delivered the asset model + staff session + migration; **enrollment UI is POS-A02**.

This package asks ChatGPT for an updated helper bootstrap that:

1. Accepts A01 as landed baseline (Core successor + workspace).
2. Prioritizes **manual add/remove skates in the UI** next.
3. Refreshes remaining gaps through rental / payment / hardware.
4. Returns bounded Cursor assignments (A02+), not another philosophy essay.

## Files

| File | Use |
| --- | --- |
| `KNOWN_BASELINE.md` | What exists after A01 |
| `GAPS_STATUS.md` | Gap IDs with DONE / PARTIAL / OPEN |
| `OPERATOR_PAIN.md` | What Stephen sees in the UI today |
| `CONSTRAINTS.md` | Hard rules (copy of project constraints) |
| `BOOTSTRAP_RETURN_SCHEMA.md` | Required ChatGPT return shape |
| `CHATGPT_REVIEW_PROMPT.md` | Paste this as the ChatGPT instruction |
| `PASTE_BUNDLE.md` | Single paste of the review materials |

## How to use with ChatGPT

1. Attach or paste `PASTE_BUNDLE.md` (or the individual files).
2. Paste `CHATGPT_REVIEW_PROMPT.md` as the instruction.
3. Expect return titled `HELPER_BOOTSTRAP_RETURN_0002` (successor bootstrap, e.g. v0.4.0).
4. Save ChatGPT’s zip/markdown under `M:\SALVAGE\` and assign the next Cursor implementation (likely POS-A02).

## Package identity

- Package ID: `SKATE_POS_GAPS_PACKAGE_GP-0002`
- Parent bootstrap: `SKATE_POS_BOOTSTRAP_0003` (v0.3.0)
- Repo branch measured: `pos-a01-asset-workspace` @ `326f873`
- A01 return: `SKATE_POS_A01_ASSET_WORKSPACE_CANDIDATE_0001.zip`
