"""Local loopback demo launch: python -m checkout_pos."""
import os
import uvicorn
from .api import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("SKATE_CHECKOUT_PORT", "8775"))
    print(f"Skate Checkout POS DEMO ONLY: http://127.0.0.1:{port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
