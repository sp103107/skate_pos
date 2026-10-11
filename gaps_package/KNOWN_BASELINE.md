# Known baseline — do not reinvent

## Product identity

- Repo: https://github.com/sp103107/skate_pos  
- Local freeze: `M:\OTHER\test_rink_rental_app\skate_pos\`  
- This is an **inventory operator companion checkpoint**, not a rental POS.

## Frozen artifacts

| Artifact | Version / ID | SHA-256 |
| --- | --- | --- |
| UI candidate | `Skate_Inventory_UI_Candidate_v0.1.0-rc.6.zip` | `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc` |
| Core capsule | `Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip` | `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3` |
| Local results | `UI01_LOCAL_AGENT_RESULTS_0003.zip` | `06d32007bb78adef578c5e9ff1991d9a2991e19e1146b350e1bb4c04d766d654` |
| rc.5 acceptance | disposition 0002 | `80254a65c5879ca0bafbfd68c6945951fca5f89f3f786e03bc51e27ea4021a47` (outer zip) |

## What works today

- Loopback UI + Core bridge on `127.0.0.1` (single process serves frontend + API)
- Local start/stop: `start_all.sh` / `.bat`, `stop_all.sh` / `.bat`
- Persistent synthetic demo DB under `.local-runtime/demo` (create once; not wiped on restart)
- Operator flows: scan by **string identifier**, inventory list, pair detail, transfer location, verify
- WSL launcher lifecycle measured PASS; native Windows launcher **NOT_RUN**

## Whitelisted Core commands (UI01 adapter)

`scan_asset`, `register_pair`, `register_component`, `link_pair`, `verify_inventory`, `transfer_location`

## Whitelisted queries

`list_inventory`, `get_pair`, `find_asset`, `asset_history`, `runtime_status`

## Explicitly gated / absent

- checkout / checkin / reserve / rental revenue flows  
- recovery / rebuild / ownership transfer  
- payment processor / QR pay  
- NFC / barcode / QR hardware drivers  
- public API, multi-tenant, production deploy  
- Android packaging  

## Acceptance flags

- Disposition 0002: `PASS_WITH_KNOWN_LIMITATIONS` (rc.5 evidence review; not fresh Judge runtime)  
- `ui_freeze=false`, `core_changed=false`, distribution `HANDOFF_ONLY`  
- Retained: F-01 stale HEALTHY, F-02 tall mobile nav, F-03 lineage note  

## Operator policy (Stephen)

- Prefer targeted functional validation  
- Non-system-breaking UI / admin findings should not stall builds  
- Independent review is not routine unless explicitly activated  
