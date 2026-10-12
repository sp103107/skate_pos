# Operator pain — what Stephen sees

## Observed after A01 launch

1. App loads with DEMO banner and staff login.
2. After sign-in (`STAFF-DEMO`), Inventory and Assets show seeded stock.
3. There is **no control to add a new skate, helmet, or Polar Bear**.
4. Scan only finds existing identifiers; unknown IDs fail — no enroll path.
5. Move/verify exist for pairs, but day-one rink stock entry is still blocked in UI.

## Operator goal (restated)

Staff at the counter must be able to:

1. **Add** individual skates (L/R, brand, size), aids, helmets — manual first.
2. Attach barcode/QR/NFC identifiers later.
3. Retire/remove safely.
4. Form a rental cart of a valid L+R set (+ optional aid/helmet).
5. Take payment (hosted QR/link; optional cash later).
6. Issue and return stock with inspection.

A01 only unlocked step 0 (data model + login + persistence). **Step 1 is the next visible win.**

## Ask for ChatGPT

Prioritize a bootstrap where the **first Cursor assignment after A01** delivers visible “Add skate” (and related enrollment) in the UI, with Core already supporting `register_asset`. Do not re-ask for another Core asset-table assignment unless a real schema hole remains.
