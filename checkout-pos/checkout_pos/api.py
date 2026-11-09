"""Demo-only loopback API for standalone Skate Checkout POS K01."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .db import CheckoutDB, CheckoutError

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


class CartLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sku: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=99)


class CartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    lines: list[CartLine] = Field(min_length=1, max_length=50)
    discount_minor: int = Field(default=0, ge=0, le=100_000_000)


class SaleRequest(CartRequest):
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")


def create_app(db_path: str | Path | None = None, tax_rate_bps: int | None = None, *, mode: str | None = None) -> FastAPI:
    resolved_mode = mode if mode is not None else os.getenv("SKATE_CHECKOUT_MODE", "demo")
    if resolved_mode != "demo":
        raise RuntimeError("LIVE_CHECKOUT_DISABLED: K01 supports demo mode only")
    if tax_rate_bps is None and os.getenv("SKATE_CHECKOUT_DEMO_TAX_BPS"):
        tax_rate_bps = int(os.environ["SKATE_CHECKOUT_DEMO_TAX_BPS"])
    target = db_path or os.getenv("SKATE_CHECKOUT_DB") or Path.home() / ".skate-pos" / "checkout-demo.db"
    database = CheckoutDB(target, tax_rate_bps=tax_rate_bps)
    app = FastAPI(title="Skate Checkout POS (Demo)", version=__version__, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def local_only_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(CheckoutError)
    async def domain_error(_request: Request, exc: CheckoutError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Invalid checkout request"}})

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html", media_type="text/html")

    @app.get("/app.js")
    def script():
        return FileResponse(FRONTEND / "app.js", media_type="text/javascript")

    @app.get("/styles.css")
    def styles():
        return FileResponse(FRONTEND / "styles.css", media_type="text/css")

    @app.get("/api/status")
    def status():
        return {"application": "skate-checkout-pos", "version": __version__, "mode": "DEMO_ONLY",
                "payments": "SIMULATED_ONLY", "paypal": "NOT_CONNECTED", "inventory": "NOT_CONNECTED",
                "tax_status": "DEMO_CONFIGURED" if database.tax_rate_bps is not None else "UNCONFIGURED"}

    @app.get("/api/catalog")
    def catalog():
        return {"items": database.catalog(), "mode": "DEMO_ONLY"}

    @app.post("/api/quote")
    def quote(request: CartRequest):
        return database.quote([line.model_dump() for line in request.lines], request.discount_minor)

    @app.post("/api/sales", status_code=201)
    def sale_create(request: SaleRequest):
        return database.create_sale(request.request_id, [line.model_dump() for line in request.lines], request.discount_minor)

    @app.get("/api/sales/{sale_id}")
    def sale_get(sale_id: str):
        return database.sale(sale_id)

    @app.post("/api/sales/{sale_id}/simulate-payment")
    def sale_demo_payment(sale_id: str):
        return database.simulate_payment(sale_id)

    return app
