# Helper bootstrap — required return schema

ChatGPT must return a single markdown document (and optionally a fenced JSON block) with **these sections in order**.  
Do not omit sections; use `TBD` with a reason if unknown.

## Markdown document title

`HELPER_BOOTSTRAP_RETURN_0001`

## Sections

### 1. Executive verdict
- 5–10 sentences: is the gap catalog complete enough to plan an MVP?
- Biggest missing decisions Stephen must make.

### 2. Confirmed baseline (no reinvention)
- Bullet list of what to keep from rc.6 / Core 0.3.1-rc.1.

### 3. Gap catalog review
For each gap ID in `GAPS_CATALOG.md` (or grouped by lane):
- `keep` / `split` / `merge` / `defer` / `add`
- One-line reason  
List any **new gap IDs** you add as `G-X##` with lane letter.

### 4. Recommended MVP slice (“First paid rental day”)
- Ordered backlog of gap IDs only  
- Explicit **out of MVP** list  
- Success criteria (operator-observable)

### 5. Bounded assignment stubs (3–6)
For each assignment stub provide:
- `assignment_id` (e.g. `POS-A01`)
- `title`
- `lane` (B/C/D/E/F)
- `goal`
- `in_scope` (bullets)
- `out_of_scope` (bullets)
- `depends_on` (assignment or gap IDs)
- `acceptance_checks` (testable)
- `return_package_name` (suggested zip name)
- `authority_ceiling` (e.g. HANDOFF_ONLY, no UI freeze)

### 6. Helper bootstrap for Cursor / local agent
Concrete starter pack:
- Folder layout to create  
- Files to draft first (names only + 1-line purpose)  
- First commands to run after authorization  
- What **not** to touch (frozen zips, Core bytes, secrets)

### 7. Hardware & vendor decision worksheet
Questions Stephen must answer, with suggested default if he wants speed:
- Kiosk OS (Windows vs Linux/Android)  
- Barcode vs NFC first  
- Payment processor  
- Printer needed on day one?

### 8. Risks & anti-patterns
- Top risks if lanes are collapsed  
- Anti-patterns (e.g. fake payment success, editing sealed Core)

### 9. Open questions for Stephen
Numbered list, max 12.

## Optional JSON block

After the markdown, optionally append:

```json
{
  "bootstrap_id": "HELPER_BOOTSTRAP_RETURN_0001",
  "mvp_gap_order": ["G-F02", "G-C01", "..."],
  "assignments": [
    {
      "assignment_id": "POS-A01",
      "title": "...",
      "lane": "B",
      "depends_on": [],
      "return_package_name": "..."
    }
  ],
  "new_gaps": [],
  "operator_decisions_required": []
}
```
