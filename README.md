# skate_pos — frozen inventory companion checkpoint

**This repository is not a rental POS and cannot take payments.**

It holds a **frozen local checkpoint** of the Skate Inventory UI companion (UI01 rc.6) bound to frozen Core `0.3.1-rc.1`, plus evidence and a gap roadmap toward a future rental kiosk / payments product.

| Field | Value |
| --- | --- |
| Status | Checkpoint / historical handoff only |
| Distribution | `HANDOFF_ONLY` |
| UI freeze | **false** |
| Release / deployment | **false** |
| Rental / checkout | **not implemented** (gated in Core for this binding) |
| Payments | **not implemented** |

## What is frozen here

| Path | Artifact | SHA-256 |
| --- | --- | --- |
| `frozen/ui/` | `Skate_Inventory_UI_Candidate_v0.1.0-rc.6.zip` | `60d902370abbbda7e403d46163ccd102bc73a6df7b4158e6718551d3716778fc` |
| `frozen/core/` | `Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip` | `40ffdac4d0eb2bbbd6dd72cce2be0ec953842eb4b34ff7934cc6bab5f53b27e3` |
| `frozen/evidence/` | `UI01_LOCAL_AGENT_RESULTS_0003.zip` | `06d32007bb78adef578c5e9ff1991d9a2991e19e1146b350e1bb4c04d766d654` |

See `MANIFEST.sha256` for full file hashes. Sidecar `.sha256` files travel with each archive.

## What this companion can do today

Trusted-local **operator inventory** UI on `127.0.0.1`:

- Scan / find asset by identifier string  
- List inventory, pair detail, transfer location, verify  
- Local start/stop scripts (`start_all` / `stop_all` inside the UI zip)  
- Synthetic demo database only  

**Not included:** rental kiosk UX, NFC/barcode/QR hardware drivers, checkout/checkin, payment processor, public API, production DB, Android packaging.

## Run locally (after extracting the UI zip)

```bash
# Linux/WSL — see LOCAL_RUN.md inside the candidate
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core.py --core-zip /path/to/Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1.zip
./start_all.sh
# open http://127.0.0.1:8765  (use 127.0.0.1, not localhost)
```

WSL lifecycle was measured PASS in results 0003. Native Windows launcher lifecycle is **NOT_RUN**.

## Docs

- [`REPO_STATUS.md`](REPO_STATUS.md) — binding, acceptance, non-claims  
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — gap lanes toward kiosk / scan / rental / payments  
- [`docs/GAPS.md`](docs/GAPS.md) — concrete gap checklist  

## Provenance

- Baseline UI rc.5 accepted `PASS_WITH_KNOWN_LIMITATIONS` (disposition 0002; evidence review, not fresh Judge runtime).  
- rc.6 adds local launchers + persistent demo workspace only.  
- Retained findings: F-01 (stale HEALTHY), F-02 (mobile nav height), F-03 (lineage note).  
- Do not substitute historical Core `0.3.0` for this binding.

Local mirror of this tree (before/while GitHub sync):  
`M:\OTHER\test_rink_rental_app\skate_pos\`
