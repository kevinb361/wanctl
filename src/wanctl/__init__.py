"""wanctl - Adaptive CAKE bandwidth control for RouterOS."""

from wanctl.build_identity import get_build_identity

_identity = get_build_identity()
__version__ = _identity["version"]
__revision__ = _identity["revision"]

__all__ = ["__revision__", "__version__"]
