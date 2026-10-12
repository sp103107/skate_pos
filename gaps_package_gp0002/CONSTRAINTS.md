# Constraints — hard rules for bootstrap advice

Any helper bootstrap from ChatGPT **must** obey these:

1. **Do not claim** the current product is a POS, payment system, or UI-frozen release.  
2. **Do not** propose editing sealed Core `0.3.1-rc.1` or UI rc.6 zips in place.  
3. **Do reuse** Core successor `0.4.0-a01.1` / `app/` copy-on-write trees; new Core work needs a **new successor identity** (e.g. 0.4.0-a02.x), not silent mutation of A01 without lineage.  
4. **Do not** put API keys, processor secrets, or production DB credentials in git or in the bootstrap text.  
5. **Do not** collapse lanes into one unbounded “build everything” arc. Prefer bounded assignments with acceptance criteria.  
6. **Preserve** adapter discipline: new Core commands need explicit bridge whitelist / contracts.  
7. **Distribution default** remains `HANDOFF_ONLY` until Stephen authorizes otherwise.  
8. **BUILD ends at CANDIDATE_COMPLETE**, never “PASS” from the builder.  
9. **BLOCKED ≠ DISABLED** for scheduler/work state.  
10. **Hardware drivers** (NFC/barcode) stay outside sealed Core archives.  
11. **Stephen’s validation policy**: only system/app-breaking issues gate routine builds; keep F-01/F-02/F-03 recorded.  
12. **Do not fake** payment success, write customer prices into settled totals, use tag IDs as authentication, or treat ambient RFID as consent.  
13. A01 already has `register_asset` — do **not** reinvent the asset table unless a concrete schema hole is shown. Prefer UI + pairing + catalog on top.  
14. Recommend tools/vendors as **options with tradeoffs**, not mandated purchases.  
