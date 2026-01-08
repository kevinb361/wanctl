"""
Steering Module - Adaptive Multi-WAN Traffic Routing

Routes latency-sensitive traffic to an alternate WAN when the primary WAN
experiences congestion. Uses multi-signal detection (RTT + CAKE drops + queue depth)
with hysteresis to prevent flapping.

Components:
- daemon.py: Main steering daemon with state machine
- cake_stats.py: CAKE queue statistics reader
- congestion_assessment.py: Multi-signal congestion assessment
- steering_confidence.py: Phase 2B confidence-based steering (optional)

Usage:
    from wanctl.steering import SteeringDaemon, CongestionState
"""

from .cake_stats import CakeStats, CakeStatsReader, CongestionSignals
from .congestion_assessment import (
    CongestionState,
    StateThresholds,
    assess_congestion_state,
    ewma_update
)
from .daemon import (
    SteeringDaemon,
    SteeringState,
    SteeringConfig,
    RouterOSController,
    RTTMeasurement,
    BaselineLoader,
)

# Phase 2B (optional)
PHASE2B_AVAILABLE = False
try:
    from . import steering_confidence as _sc
    PHASE2B_AVAILABLE = bool(_sc)  # Reference to satisfy linters
except ImportError:
    pass

__all__ = [
    # Core classes
    'SteeringDaemon',
    'SteeringState',
    'SteeringConfig',
    'RouterOSController',
    'RTTMeasurement',
    'BaselineLoader',
    # CAKE statistics
    'CakeStats',
    'CakeStatsReader',
    'CongestionSignals',
    # Congestion assessment
    'CongestionState',
    'StateThresholds',
    'assess_congestion_state',
    'ewma_update',
    # Phase 2B (if available)
    'PHASE2B_AVAILABLE',
]

# Add Phase2B exports if available
if PHASE2B_AVAILABLE:
    # Re-export Phase2B symbols (referenced via _sc for linter compatibility)
    Phase2BController = _sc.Phase2BController
    ConfidenceSignals = _sc.ConfidenceSignals
    ConfidenceWeights = _sc.ConfidenceWeights
    TimerState = _sc.TimerState
    compute_confidence = _sc.compute_confidence
    __all__.extend([
        'Phase2BController',
        'ConfidenceSignals',
        'ConfidenceWeights',
        'TimerState',
        'compute_confidence',
    ])
