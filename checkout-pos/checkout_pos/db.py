"""SQLite-backed demo sales ledger. No payment credentials or live charges."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CheckoutError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class CheckoutDB:
    def __init__(self, path: str | Path, tax_rate_bps: int | None = None):
        self.path = Path(path)
        if tax_rate_bps is not None and not (0 <= tax_rate_bps <= 10000):
            raise ValueError("tax_rate_bps out of range")
        self.tax_rate_bps = tax_rate_bps
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 10000")
        return con

    def initialize(self) -> None:
        with closing(self._connect()) as con:
            con.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS catalog_items (
                    sku TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL
                    CHECK(kind IN ('RETAIL','RENTAL_DEMO')),
                    price_minor INTEGER NOT NULL CHECK(price_minor >= 0),
                    currency TEXT NOT NULL DEFAULT 'USD',
                    tax_category TEXT NOT NULL CHECK(tax_category IN ('STANDARD','EXEMPT')),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('DRAFT','SIMULATED_PAID')),
                    subtotal_minor INTEGER NOT NULL,
                    discount_minor INTEGER NOT NULL,
                    tax_minor INTEGER NOT NULL,
                    total_minor INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    tax_status TEXT NOT NULL,
                    tax_rate_bps INTEGER,
                    created_at TEXT NOT NULL,
                    paid_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sale_lines (
                    sale_id TEXT NOT NULL REFERENCES sales(sale_id),
                    line_number INTEGER NOT NULL,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price_minor INTEGER NOT NULL,
                    extended_minor INTEGER NOT NULL,
                    discount_minor INTEGER NOT NULL,
                    tax_minor INTEGER NOT NULL,
                    tax_category TEXT NOT NULL,
                    PRIMARY KEY(sale_id, line_number)
                );
            """)
            seed = [
                ("SKATE-RENTAL-DEMO", "Skate rental (demo, not issued)", "RENTAL_DEMO", 1000, "USD", "STANDARD"),
                ("FRIES", "French fries", "RETAIL", 500, "USD", "STANDARD"),
                ("HOT-DOG", "Hot dog", "RETAIL", 400, "USD", "STANDARD"),
                ("WATER", "Bottled water", "RETAIL", 200, "USD", "STANDARD"),
            ]
            con.executemany("INSERT OR IGNORE INTO catalog_items(sku,name,kind,price_minor,currency,tax_category) VALUES(?,?,?,?,?,?)", seed)

    def catalog(self) -> list[dict]:
        with closing(self._connect()) as con:
            return [dict(row) for row in con.execute("SELECT sku,name,kind,price_minor,currency,tax_category FROM catalog_items WHERE active=1 ORDER BY kind, name, sku")]

    def _quote_in_conn(self, con: sqlite3.Connection, raw_lines: list[dict], discount_minor: int) -> dict:
        if not 1 <= len(raw_lines) <= 50:
            raise CheckoutError("CART_INVALID", "Cart requires 1–50 line items")
        if discount_minor < 0:
            raise CheckoutError("DISCOUNT_INVALID", "Discount cannot be negative")
        seen: set[str] = set()
        lines = []
        currency = None
        for raw in raw_lines:
            sku, quantity = raw["sku"], raw["quantity"]
            if sku in seen:
                raise CheckoutError("DUPLICATE_SKU", f"Duplicate cart SKU {sku}")
            seen.add(sku)
            if not 1 <= quantity <= 99:
                raise CheckoutError("QUANTITY_INVALID", "Quantity must be 1–99")
            row = con.execute("SELECT * FROM catalog_items WHERE sku=? AND active=1", (sku,)).fetchone()
            if row is None:
                raise CheckoutError("SKU_UNAVAILABLE", f"Unknown or inactive SKU: {sku}")
            if currency is not None and currency != row["currency"]:
                raise CheckoutError("CURRENCY_MIXED", "Cart must use one currency")
            currency = row["currency"]
            extended = row["price_minor"] * quantity
            lines.append({"sku": sku, "name": row["name"], "kind": row["kind"], "quantity": quantity,
                          "unit_price_minor": row["price_minor"], "extended_minor": extended,
                          "tax_category": row["tax_category"]})
        subtotal = sum(l["extended_minor"] for l in lines)
        if discount_minor > subtotal:
            raise CheckoutError("DISCOUNT_EXCEEDS_SUBTOTAL", "Discount exceeds subtotal")
        # Allocate cart discount deterministically and exactly, including the remainder.
        # Keeps tax and future line-item price snapshots internally consistent.
        base_allocations = []
        if subtotal:
            for idx, line in enumerate(lines):
                numerator = discount_minor * line["extended_minor"]
                base_allocations.append([numerator // subtotal, numerator % subtotal, idx])
            remainder = discount_minor - sum(x[0] for x in base_allocations)
            for _, _, idx in sorted(base_allocations, key=lambda x: (-x[1], x[2]))[:remainder]:
                base_allocations[idx][0] += 1
        else:
            base_allocations = [[0, 0, idx] for idx, _ in enumerate(lines)]
        taxes = 0
        for idx, line in enumerate(lines):
            line["discount_minor"] = base_allocations[idx][0]
            taxable = line["extended_minor"] - line["discount_minor"]
            rate = self.tax_rate_bps if line["tax_category"] == "STANDARD" else 0
            line["tax_minor"] = (taxable * rate + 5000) // 10000 if rate is not None else 0
            taxes += line["tax_minor"]
        return {"lines": lines, "subtotal_minor": subtotal, "discount_minor": discount_minor,
                "tax_minor": taxes, "total_minor": subtotal - discount_minor + taxes,
                "currency": currency, "tax_rate_bps": self.tax_rate_bps,
                "tax_status": "DEMO_CONFIGURED" if self.tax_rate_bps is not None else "UNCONFIGURED",
                "mode": "DEMO_ONLY", "inventory_effect": "NONE"}

    def quote(self, lines: list[dict], discount_minor: int = 0) -> dict:
        with closing(self._connect()) as con:
            return self._quote_in_conn(con, lines, discount_minor)

    def create_sale(self, request_id: str, lines: list[dict], discount_minor: int = 0) -> dict:
        request = {"lines": lines, "discount_minor": discount_minor}
        request_hash = canonical_hash(request)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("SELECT sale_id,request_hash FROM sales WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise CheckoutError("IDEMPOTENCY_CONFLICT", "Request ID reused with different cart", 409)
                result = self._sale_in_conn(con, existing["sale_id"])
                con.execute("COMMIT")
                return result
            quote = self._quote_in_conn(con, lines, discount_minor)
            sale_id = "SALE-" + uuid.uuid4().hex.upper()[:16]
            con.execute("INSERT INTO sales(sale_id,request_id,request_hash,status,subtotal_minor,discount_minor,tax_minor,total_minor,currency,tax_status,tax_rate_bps,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sale_id, request_id, request_hash, "DRAFT", quote["subtotal_minor"], discount_minor,
                         quote["tax_minor"], quote["total_minor"], quote["currency"], quote["tax_status"],
                         quote["tax_rate_bps"], utc_now()))
            for idx, line in enumerate(quote["lines"], 1):
                con.execute("INSERT INTO sale_lines(sale_id,line_number,sku,name,kind,quantity,unit_price_minor,extended_minor,discount_minor,tax_minor,tax_category) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (sale_id, idx, *(line[k] for k in ["sku", "name", "kind", "quantity", "unit_price_minor", "extended_minor", "discount_minor", "tax_minor", "tax_category"])))
            result = self._sale_in_conn(con, sale_id)
            con.execute("COMMIT")
            return result
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def _sale_in_conn(self, con: sqlite3.Connection, sale_id: str) -> dict:
        row = con.execute("SELECT * FROM sales WHERE sale_id=?", (sale_id,)).fetchone()
        if row is None:
            raise CheckoutError("SALE_NOT_FOUND", "Sale not found", 404)
        result = dict(row)
        result.pop("request_hash", None)
        result["lines"] = [dict(line) for line in con.execute("SELECT sku,name,kind,quantity,unit_price_minor,extended_minor,discount_minor,tax_minor,tax_category FROM sale_lines WHERE sale_id=? ORDER BY line_number", (sale_id,))]
        result["mode"] = "DEMO_ONLY"
        result["inventory_effect"] = "NONE"
        return result

    def sale(self, sale_id: str) -> dict:
        with closing(self._connect()) as con:
            return self._sale_in_conn(con, sale_id)

    def simulate_payment(self, sale_id: str) -> dict:
        """Demo-only state change. NOT a PayPal payment or authorization."""
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            sale = con.execute("SELECT status FROM sales WHERE sale_id=?", (sale_id,)).fetchone()
            if not sale:
                raise CheckoutError("SALE_NOT_FOUND", "Sale not found", 404)
            if sale["status"] == "DRAFT":
                con.execute("UPDATE sales SET status='SIMULATED_PAID', paid_at=? WHERE sale_id=? AND status='DRAFT'", (utc_now(), sale_id))
            result = self._sale_in_conn(con, sale_id)
            con.execute("COMMIT")
            return result
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
