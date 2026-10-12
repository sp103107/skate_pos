# Non-claims — rc.5

- rc.5 local results (checks, browser UIB01–UIB11, supplemental navigation/focus/workflow measurements, screenshots) are scoped operator measurements on one WSL2 machine, not independent Judge PASS, UI01 completion, UI freeze, release, promotion or deployment.
- Only `frontend/app.css` changed functionally. No Core edits, no adapter/app.js/adapter.js/contracts/tests/scripts changes, no new dependencies, no feature expansion, no UI-polish integration.
- The navigation now wraps at ≤1050px (nav block height at 390px wide ≈210px vs 68px for the rc.4 scrolling row). This is a deliberate trade-off chosen because Chromium does not scroll a partially visible item into view on keyboard focus, so a horizontal scroll nav cannot keep focus unclipped with CSS alone. Any alternative (e.g. JS focus-scroll) is outside the authorized CSS repair and is recorded, not implemented.
- Type checking remains checkJs/noEmit ES2022, not strict mode. Browser proof is for Chromium 151.0.7922.34 headless only; no other browsers/devices.
- `context/` rc.4 entries and `precommit_head` 35 are historical; `context/RC5_LOCAL_BUILD_RECORD.json` is a local build record, not a relay head. No communications surfaces were used or activated.
- No production DB/data, rental/public API/recovery expansion, persistent service, credentials/session repurposing, live MCP/VPort/registry, agent integration or role transfer.
- Historical rc.1–rc.4 evidence is immutable history under `history/`, not current proof. Results archive 0001 is unchanged; `history/rc4_evidence/BASELINE_EVIDENCE_CORRECTIONS.md` corrects its interpretation only.
