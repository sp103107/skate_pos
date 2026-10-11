# Constraints — hard rules for bootstrap advice

Any helper bootstrap from ChatGPT **must** obey these:

1. **Do not claim** the current freeze is a POS, payment system, or UI-frozen release.  
2. **Do not** propose editing sealed Core `0.3.1-rc.1` bytes in place; Core changes need a successor identity.  
3. **Do not** put API keys, processor secrets, or production DB credentials in git or in the bootstrap text.  
4. **Do not** collapse lanes into one unbounded “build everything” arc. Prefer bounded assignments with acceptance criteria.  
5. **Preserve** UI01 adapter discipline: new Core commands need explicit whitelist / contract work.  
6. **Prefer** copy-on-write successors (rc.7+, Core successors) over mutating frozen zips.  
7. **Distribution default** remains `HANDOFF_ONLY` until Stephen authorizes otherwise.  
8. **BUILD ends at CANDIDATE_COMPLETE**, never “PASS” from the builder. Independent validation is separate.  
9. **Scheduler / work state**: BLOCKED ≠ DISABLED; do not advise disabling automation because work is blocked.  
10. **Hardware drivers** (NFC/barcode) stay outside sealed Core archives.  
11. **Stephen’s validation policy**: only system/app-breaking issues should gate routine builds; keep known UI debt recorded.  
12. Bootstrap may recommend tools/vendors (Stripe vs Square, NFC brands) as **options with tradeoffs**, not as mandated purchases.  
