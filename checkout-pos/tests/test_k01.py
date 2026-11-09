"""K01 direct API and persistence assertions; demo mode only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from checkout_pos.api import create_app
from checkout_pos.db import CheckoutDB, CheckoutError


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(db_path=tmp_path / "kiosk.db")) as api:
        yield api


def cart(*lines, discount_minor=0):
    return {"lines": [{"sku": sku, "quantity": qty} for sku, qty in lines], "discount_minor": discount_minor}


def test_k01_status_prohibits_live_payments(client):
    state = client.get("/api/status").json()
    assert state["mode"] == "DEMO_ONLY" and state["payments"] == "SIMULATED_ONLY"
    assert state["paypal"] == "NOT_CONNECTED" and state["inventory"] == "NOT_CONNECTED"
    assert state["tax_status"] == "UNCONFIGURED"
    with pytest.raises(RuntimeError, match="LIVE_CHECKOUT_DISABLED"):
        create_app(db_path="unused.db", mode="real")


def test_catalog_seeds_expected_products(client):
    items = client.get("/api/catalog").json()["items"]
    assert {i["sku"] for i in items} == {"SKATE-RENTAL-DEMO", "FRIES", "HOT-DOG", "WATER"}
    assert all(i["currency"] == "USD" for i in items)
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200


def test_quote_server_calculates_amounts_no_tax_rule(client):
    r = client.post("/api/quote", json=cart(("FRIES", 2), ("WATER", 1), discount_minor=100))
    assert r.status_code == 200
    q = r.json()
    assert q["subtotal_minor"] == 1200 and q["discount_minor"] == 100
    assert q["total_minor"] == 1100 and q["tax_minor"] == 0
    assert q["tax_status"] == "UNCONFIGURED"
    assert sum(l["discount_minor"] for l in q["lines"]) == 100


def test_quote_configurable_demo_tax_and_exempt(tmp_path):
    db = CheckoutDB(tmp_path / "tax.db", tax_rate_bps=700)
    quote = db.quote([{"sku": "HOT-DOG", "quantity": 1}], 0)
    assert quote["tax_minor"] == 28 and quote["total_minor"] == 428
    assert quote["tax_status"] == "DEMO_CONFIGURED"
    with closing(db._connect()) as conn:
        conn.execute("UPDATE catalog_items SET tax_category='EXEMPT' WHERE sku='WATER'")
    q = db.quote([{"sku": "WATER", "quantity": 1}], 0)
    assert q["tax_minor"] == 0
    with pytest.raises(ValueError):
        CheckoutDB(tmp_path / "bad.db", tax_rate_bps=-1)


def test_quote_discounts_are_allocated_exactly(tmp_path):
    db = CheckoutDB(tmp_path / "tax.db", tax_rate_bps=500)
    q = db.quote([{"sku":"FRIES","quantity":1}, {"sku":"WATER","quantity":1}, {"sku":"HOT-DOG","quantity":1}], 101)
    assert q["discount_minor"] == 101
    assert sum(x["discount_minor"] for x in q["lines"]) == 101
    assert q["total_minor"] == q["subtotal_minor"] - 101 + q["tax_minor"]


def test_draft_sale_and_payment_simulation_preserve_snapshot(client):
    input_data = {"request_id":"request-0001", **cart(("SKATE-RENTAL-DEMO", 1), ("WATER", 2))}
    r = client.post("/api/sales", json=input_data)
    assert r.status_code == 201
    sale = r.json()
    assert sale["status"] == "DRAFT" and sale["total_minor"] == 1400
    assert sale["inventory_effect"] == "NONE" and sale["mode"] == "DEMO_ONLY"
    assert sum(i["unit_price_minor"]*i["quantity"] for i in sale["lines"]) == 1400
    payment = client.post(f"/api/sales/{sale['sale_id']}/simulate-payment", json={})
    assert payment.status_code == 200
    paid = payment.json()
    assert paid["status"] == "SIMULATED_PAID" and paid["paid_at"]
    assert paid == client.post(f"/api/sales/{sale['sale_id']}/simulate-payment", json={}).json()
    assert paid == client.get(f"/api/sales/{sale['sale_id']}").json()


def test_request_id_retries_and_mismatch_are_detected(client):
    body = {"request_id":"request-0002", **cart(("FRIES",1))}
    first = client.post("/api/sales", json=body).json()
    replay = client.post("/api/sales", json=body).json()
    assert first == replay
    conflict = client.post("/api/sales", json={**body, **cart(("FRIES",2))})
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_reject_unknown_duplicate_and_negative_inputs(client):
    bads = [
        (cart(("UNKNOWN",1)), "SKU_UNAVAILABLE"),
        (cart(("FRIES",1), ("FRIES",2)), "DUPLICATE_SKU"),
        (cart(("WATER",1), discount_minor=250), "DISCOUNT_EXCEEDS_SUBTOTAL"),
    ]
    for body, code in bads:
        result=client.post("/api/quote",json=body)
        assert result.status_code == 422 and result.json()["error"]["code"] == code
    assert client.post("/api/quote",json=cart(("FRIES",-2))).status_code == 422
    assert client.post("/api/quote",json={"lines":[],"discount_minor":0}).status_code == 422
    assert client.post("/api/quote",json=cart(("FRIES", 1))|{"total_minor":1}).status_code == 422


def test_unauthenticated_real_payment_api_absent(client):
    for route in ["/api/paypal/create-order", "/api/paypal/capture", "/api/refunds", "/api/inventory/issue"]:
        assert client.post(route, json={}).status_code == 404
    assert client.get("/api/sales/NO_SUCH_SALE").status_code == 404


def test_concurrent_duplicate_request_returns_single_sale(tmp_path):
    db = CheckoutDB(tmp_path / "race.db")
    body = ([{"sku":"FRIES","quantity":1}], 0)
    def write(_): return db.create_sale("raced-0001", *body)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(write, range(9)))
    assert len({r["sale_id"] for r in results}) == 1
    with closing(db._connect()) as con:
        assert con.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1


def test_price_snapshot_is_not_mutated_by_catalog_edits(tmp_path):
    db = CheckoutDB(tmp_path / "snapshot.db")
    body = [{"sku":"WATER", "quantity":2}]
    before = db.create_sale("snapshot-0001", body)
    with closing(db._connect()) as con:
        con.execute("UPDATE catalog_items SET price_minor=999 WHERE sku='WATER'")
    after = db.sale(before["sale_id"])
    assert before == after
    assert db.quote(body)["total_minor"] == 1998


def test_sessions_no_sensitive_values_in_public_payload(client):
    for route in ("/api/status", "/api/catalog"):
        data = client.get(route).text.lower()
        for secret in ("client_secret", "access_token", "paypal_client_id", "customer_email"):
            assert secret not in data
