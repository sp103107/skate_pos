# Repository status — skate_pos checkpoint

Recorded for the initial GitHub freeze of the UI01 local companion.

## Identity

| Item | Value |
| --- | --- |
| Repo | https://github.com/sp103107/skate_pos |
| Local freeze root | `M:\OTHER\test_rink_rental_app\skate_pos\` |
| UI candidate | `0.1.0-rc.6` |
| UI SHA-256 | `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc` |
| Core dependency | `0.3.1-rc.1` / `0.3.1rc1` wheel |
| Core SHA-256 | `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3` |
| Results package | `UI01_LOCAL_AGENT_RESULTS_0003` |
| Results SHA-256 | `06d32007bb78adef578c5e9ff1991d9a2991e19e1146b350e1bb4c04d766d654` |

## Acceptance (scoped)

- Disposition 0002: **PASS_WITH_KNOWN_LIMITATIONS** for rc.5 trusted-local runtime/build handoff (independent evidence review; not a fresh Judge runtime suite).  
- rc.6: launcher successor; WSL lifecycle **PASS**; native Windows **NOT_RUN**.  
- Flags: `ui_freeze=false`, `core_changed=false`, distribution **HANDOFF_ONLY**.

## Non-claims

- Not a rental kiosk or POS.  
- Not payment-capable.  
- Not production-deployed.  
- Not a public API or multi-tenant service.  
- Synthetic demo data only in the companion launch path.  
- Checkout / checkin / reserve / recovery remain **gated** at the UI01 Core adapter boundary.

## Whitelisted Core operations (this binding)

`scan_asset`, `register_pair`, `register_component`, `link_pair`, `verify_inventory`, `transfer_location`

Queries: `list_inventory`, `get_pair`, `find_asset`, `asset_history`, `runtime_status`
