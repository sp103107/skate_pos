# POS-A01 non-claims

- Status is **CANDIDATE_COMPLETE**, not Judge PASS, UI freeze, release, or deploy.
- Distribution is **HANDOFF_ONLY**. `ui_freeze=false`.
- Sealed `frozen/` archives (UI rc.6, Core 0.3.1-rc.1, results 0003) were **not** modified.
- No checkout, payment, NFC/RFID drivers, or live-data activation.
- Local pytest results are scoped operator measurement, not independent review.
- Core packaging/version identity tests that assert `0.3.1rc1` are expected to fail against successor `0.4.0a1`; substantive registry/spine suites are the regression gate.
- Demo PIN material in `config/staff.example.json` is synthetic only.
