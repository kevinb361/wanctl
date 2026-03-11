"""Dashboard widget components.

Re-exports: WanPanel, SteeringPanel, StatusBar.
"""

from wanctl.dashboard.widgets.status_bar import StatusBar
from wanctl.dashboard.widgets.steering_panel import SteeringPanel
from wanctl.dashboard.widgets.wan_panel import WanPanel

__all__ = ["WanPanel", "SteeringPanel", "StatusBar"]
