# Helper bootstrap — required return schema (GP-0002)

ChatGPT must return a single markdown document (and optionally a fenced JSON block) with **these sections in order**.  
Do not omit sections; use `TBD` with a reason if unknown.

## Markdown document title

`HELPER_BOOTSTRAP_RETURN_0002`

(This supersedes return 0001 / bootstrap v0.3.0 for planning. Do not re-issue A01 as the first assignment.)

## Sections

### 1. Executive verdict
- 5–10 sentences: given A01 landed, is the remaining path clear?
- Confirm that “can’t add skates in UI” is an **A02 enrollment gap**, not an A01 failure.
- Biggest decisions Stephen must still make.

### 2. Confirmed baseline (no reinvention)
- What to keep from A01 (`app/`, `core-successor/`, staff session, r03 assets).
- What remains frozen under `frozen/`.

### 3. Gap status review
For each ID in `GAPS_STATUS.md` (or grouped by lane):
- `keep` / `split` / `merge` / `defer` / `add` / `done`
- One-line reason  
List any **new gap IDs** as `G-X##`.

### 4. Recommended next slice (“Staff can stock the rack”)
- Ordered backlog starting with **enrollment UI**
- Explicit out of this slice
- Operator-observable success: staff can add L/R skates, aid, helmet and see them in Assets/Inventory after refresh/restart

### 5. Bounded assignment stubs (3–6)
For each stub:
- `assignment_id` (start at **POS-A02** or justified rename)
- `title`, `lane`, `goal`
- `in_scope` / `out_of_scope`
- `depends_on`
- `acceptance_checks` (testable; include UI + API)
- `return_package_name`
- `authority_ceiling` (HANDOFF_ONLY, no UI freeze)

At least one stub must deliver **manual add skate in the UI**.

### 6. Helper bootstrap for Cursor / local agent
- Work from branch `pos-a01-asset-workspace` (or successor branch)
- Files to add/change first (enrollment panel, price catalog seed, pairing helpers)
- First commands after authorization
- What **not** to touch

### 7. Hardware & vendor decision worksheet
Refresh open questions; mark which are blocking for A02 vs later:
- Counter OS, Polar Bear label, tax, cash toggle, merchant account, NFC/RFID, waiver

### 8. Risks & anti-patterns
- Rebuilding Core asset tables unnecessarily
- Enrollment without staff session
- Skipping flexible pairing rules
- Collapsing A02+A03 into one mega-assignment

### 9. Paste-ready Cursor kickoff
A short directive Stephen can paste to Cursor to start the **next** assignment only (default POS-A02).

## Optional JSON block

```json
{
  "bootstrap_id": "SKATE_POS_BOOTSTRAP_0004",
  "supersedes": "SKATE_POS_BOOTSTRAP_0003",
  "next_assignment": "POS-A02",
  "mvp_gap_order": [],
  "out_of_mvp": [],
  "open_questions": []
}
```
