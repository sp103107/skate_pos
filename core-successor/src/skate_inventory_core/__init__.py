"""C01 trusted-local composition of the existing Skate Inventory runtime."""

from .facades import CoreRequestError
from .core import CoreConfig, CoreLifecycleError, SkateInventoryCore

__version__ = "0.4.0a1"
__all__ = ["CoreConfig", "CoreLifecycleError", "SkateInventoryCore", "CoreRequestError"]
