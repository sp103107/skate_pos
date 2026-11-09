# Skate Checkout POS — POS-K01

**State:** `LOCAL_K01_CANDIDATE` · `DEMO_ONLY` · `HANDOFF_ONLY` · `ui_freeze=false`.

An independent checkout application inside `sp103107/skate_pos`. It does not require the inventory Core, reserve equipment, charge a payment method, or communicate with PayPal. Rental catalog entries in K01 are explicitly **demo sales only**.

## Run locally (Python 3.11+; Windows/Linux)

```powershell
cd checkout-pos
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m checkout_pos
```

On Linux replace `.venv\Scripts\python.exe` with `.venv/bin/python`.
Open **http://127.0.0.1:8775**. The server binds loopback only and runs **demo-only**, including the `Simulate payment` button. Database is stored by default in the user's home directory (`~/.skate-pos/checkout-demo.db`), not in the Git repository. Override with `SKATE_CHECKOUT_DB` for local testing.

```bash
python -m pytest -q tests
```

## K01 features
- Retail and demo-rental product catalog; seeded prices in integer US cents (edit later from the authoritative business pricing plan).
- Accessible touchscreen-friendly cart with quantities and discount, server-calculated quote and explicit tax configuration state.
- Atomic SQLite draft sale creation, immutable line price snapshot, idempotent request IDs and conflict rejection.
- Demo-only simulated payment, repeat-safe transition and printable demo receipt. **No real financial settlement.**
- FastAPI server-side input validation; no external frontend CDNs or API keys.

Optional `SKATE_CHECKOUT_DEMO_TAX_BPS=700` sets a **hypothetical** demo 7% rate. This is not a determination of local tax applicability or legal treatment of any SKU. Without that environment variable, tax shows **UNCONFIGURED** and no tax is calculated. Prices, tax rules, cash handling and customer identity must be verified before activation.

## Integration boundary

Next arc `POS-K02`: PayPal **Sandbox** Orders v2 integration, server-side create/capture, verified webhooks, webhook idempotency, recovery, and public HTTPS callback requirements. No PayPal API calls, credentials, SDK or hardware are in K01.

`POS-K03`: explicit inventory/checkout envelope contract, transactional rental holds/issue/return, paid-but-unfulfilled recovery. Inventory remains authoritative for custody. `POS-K04`: physical Windows kiosk UI and native runtime validation.

## Prohibited claims / changes
- Not a live payment POS, tax-compliant register, deployed site, merchant terminal, or inventory checkout.
- No real-mode activation. `SKATE_CHECKOUT_MODE=real` deliberately refuses startup.
- Do not commit PayPal secrets, staff PINs, production databases or customer information.
- Do not merge to `main` without separate approval; preserve `frozen/` byte-for-byte.
