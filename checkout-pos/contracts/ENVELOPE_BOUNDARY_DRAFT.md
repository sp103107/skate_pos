# K03 draft interface — NOT ACTIVE

K01 runs standalone and exposes no inventory envelope endpoint. Keep the eventual integration narrow:

- `CHECKOUT_QUOTE_REQUESTED`: inventory/Core -> POS. Correlation ID, inventory hold ID, venue ID, SKU references. POS reprices server-side; inventory prices are not trusted as payment authority.
- `PAYMENT_CAPTURED`: POS -> inventory. Correlation ID, sale ID, provider capture ID, currency, authoritative amount, idempotency key, authenticated source. Inventory issues equipment only against a matching active hold.
- `FULFILLMENT_FAILED`: inventory -> POS, mark paid-but-unfulfilled; reconcile/retry/refund by separate explicit policy.
- Use authenticated durable inbox/outbox processing, bounded retries, replay protection, schema versioning and acknowledgements. Do not equate PayPal browser success with capture verification.
- Future VPort identifiers are routing aliases; without configured transport/provider bindings these messages are not delivered.
- Live PayPal, merchant access and inventory custody mutation are **not authorized** by K01.
