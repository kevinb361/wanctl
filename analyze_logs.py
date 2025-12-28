#!/usr/bin/env python3
"""
Dual-WAN CAKE Log Analyzer
Read-only analysis of autorate and steering logs
Produces daily and overall summaries in CSV and JSON format

Aligns with control spines:
1. Autorate congestion control (GREEN/YELLOW/SOFT_RED/RED states)
2. Inter-WAN steering authority (SPECTRUM_GOOD/SPECTRUM_DEGRADED)
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class AutorateEvent:
    """Single autorate measurement cycle"""
    timestamp: str
    state_dl: str  # GREEN/YELLOW/SOFT_RED/RED
    state_ul: str  # GREEN/YELLOW/RED
    rtt_instant: float
    rtt_load_ewma: float
    rtt_baseline: float
    rtt_delta: float
    bandwidth_dl: int  # Mbps
    bandwidth_ul: int  # Mbps


@dataclass
class SteeringEvent:
    """Single steering assessment"""
    timestamp: str
    steering_state: str  # SPECTRUM_GOOD/SPECTRUM_DEGRADED
    rtt_delta: float
    rtt_ewma: float
    drops: int
    queue: int
    congestion: str  # GREEN/YELLOW/RED


@dataclass
class SteeringAction:
    """Steering enable/disable event"""
    timestamp: str
    action: str  # "enable" or "disable"


@dataclass
class StateTransition:
    """State change event"""
    timestamp: str
    direction: str  # "download" or "upload" or "steering"
    from_state: str
    to_state: str
    duration_seconds: float  # Time in previous state


@dataclass
class DailySummary:
    """Summary for one day"""
    date: str

    # Autorate metrics
    autorate_cycles: int
    state_distribution_dl: Dict[str, int]  # {GREEN: 12345, YELLOW: 678, ...}
    state_distribution_ul: Dict[str, int]
    state_duration_dl: Dict[str, float]  # {GREEN: 86123.4, YELLOW: 277.1, ...} in seconds
    state_duration_ul: Dict[str, float]

    # RTT metrics
    rtt_baseline_mean: float
    rtt_baseline_min: float
    rtt_baseline_max: float
    rtt_delta_mean: float
    rtt_delta_p50: float
    rtt_delta_p95: float
    rtt_delta_p99: float
    rtt_delta_max: float

    # Bandwidth metrics
    bandwidth_dl_mean: int
    bandwidth_dl_min: int
    bandwidth_dl_max: int
    bandwidth_ul_mean: int
    bandwidth_ul_min: int
    bandwidth_ul_max: int

    # Steering metrics
    steering_cycles: int
    steering_distribution: Dict[str, int]  # {SPECTRUM_GOOD: 12345, SPECTRUM_DEGRADED: 23}
    steering_duration: Dict[str, float]  # Seconds in each state
    steering_enables: int
    steering_disables: int
    steering_total_duration_active: float  # Seconds with steering enabled

    # Congestion assessment (from steering)
    congestion_distribution: Dict[str, int]  # {GREEN: 12000, YELLOW: 300, RED: 45}

    # Transitions
    dl_transitions: List[str]  # ["GREEN→YELLOW 12:34:56", ...]
    ul_transitions: List[str]
    steering_transitions: List[str]

    # Hourly distribution (for peak hour analysis)
    cycles_by_hour: Dict[int, int]  # {0: 120, 1: 119, ..., 23: 121}
    soft_red_by_hour: Dict[int, int]  # Count of SOFT_RED states per hour
    red_by_hour: Dict[int, int]
    steering_active_by_hour: Dict[int, int]


@dataclass
class OverallSummary:
    """Overall summary across all days"""
    start_date: str
    end_date: str
    total_days: int
    total_cycles: int

    # Aggregate state distributions
    state_distribution_dl: Dict[str, int]
    state_distribution_ul: Dict[str, int]
    state_duration_dl: Dict[str, float]
    state_duration_ul: Dict[str, float]

    # Aggregate RTT metrics
    rtt_baseline_overall_mean: float
    rtt_delta_overall_mean: float
    rtt_delta_overall_p95: float
    rtt_delta_overall_p99: float
    rtt_delta_overall_max: float

    # Aggregate steering metrics
    total_steering_cycles: int
    steering_distribution: Dict[str, int]
    steering_duration: Dict[str, float]
    total_steering_enables: int
    total_steering_disables: int
    steering_total_duration_active: float

    # Aggregate congestion distribution
    congestion_distribution: Dict[str, int]

    # Transition counts
    dl_transition_counts: Dict[str, int]  # {GREEN→YELLOW: 45, ...}
    ul_transition_counts: Dict[str, int]
    steering_transition_counts: Dict[str, int]

    # Daily summaries
    daily_summaries: List[DailySummary]


# =============================================================================
# LOG PARSING
# =============================================================================

class LogParser:
    """Parse autorate and steering logs"""

    # Regex patterns
    AUTORATE_STATUS = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ '
        r'\[.*?\] \[INFO\] \w+: '
        r'\[(?P<state_dl>\w+)/(?P<state_ul>\w+)\] '
        r'RTT=(?P<rtt>\d+\.?\d*)ms, '
        r'load_ewma=(?P<load_ewma>\d+\.?\d*)ms, '
        r'baseline=(?P<baseline>\d+\.?\d*)ms, '
        r'delta=(?P<delta>-?\d+\.?\d*)ms \| '
        r'DL=(?P<dl>\d+)M, '
        r'UL=(?P<ul>\d+)M'
    )

    STEERING_STATUS = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ '
        r'\[Steering\] \[INFO\] '
        r'\[(?P<state>SPECTRUM_\w+)\] '
        r'rtt=(?P<rtt>\d+\.?\d*)ms '
        r'ewma=(?P<ewma>\d+\.?\d*)ms '
        r'drops=(?P<drops>\d+) '
        r'q=(?P<queue>\d+) \| '
        r'congestion=(?P<congestion>\w+)'
    )

    STEERING_ACTION = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ '
        r'\[Steering\] \[INFO\] '
        r'(?P<action>Enabling|Disabling) adaptive steering rule'
    )

    def __init__(self):
        self.autorate_events: List[AutorateEvent] = []
        self.steering_events: List[SteeringEvent] = []
        self.steering_actions: List[SteeringAction] = []

    def parse_autorate_log(self, log_path: Path):
        """Parse autorate log file"""
        print(f"Parsing autorate log: {log_path}")
        count = 0

        with open(log_path, 'r') as f:
            for line in f:
                match = self.AUTORATE_STATUS.search(line)
                if match:
                    self.autorate_events.append(AutorateEvent(
                        timestamp=match.group(1),
                        state_dl=match.group('state_dl'),
                        state_ul=match.group('state_ul'),
                        rtt_instant=float(match.group('rtt')),
                        rtt_load_ewma=float(match.group('load_ewma')),
                        rtt_baseline=float(match.group('baseline')),
                        rtt_delta=float(match.group('delta')),
                        bandwidth_dl=int(match.group('dl')),
                        bandwidth_ul=int(match.group('ul'))
                    ))
                    count += 1

        print(f"  Found {count} autorate events")

    def parse_steering_log(self, log_path: Path):
        """Parse steering log file"""
        print(f"Parsing steering log: {log_path}")
        status_count = 0
        action_count = 0

        with open(log_path, 'r') as f:
            for line in f:
                # Check for steering status
                match = self.STEERING_STATUS.search(line)
                if match:
                    self.steering_events.append(SteeringEvent(
                        timestamp=match.group(1),
                        steering_state=match.group('state'),
                        rtt_delta=float(match.group('rtt')),
                        rtt_ewma=float(match.group('ewma')),
                        drops=int(match.group('drops')),
                        queue=int(match.group('queue')),
                        congestion=match.group('congestion')
                    ))
                    status_count += 1
                    continue

                # Check for steering actions
                match = self.STEERING_ACTION.search(line)
                if match:
                    action = "enable" if match.group('action') == "Enabling" else "disable"
                    self.steering_actions.append(SteeringAction(
                        timestamp=match.group(1),
                        action=action
                    ))
                    action_count += 1

        print(f"  Found {status_count} steering status events")
        print(f"  Found {action_count} steering actions")


# =============================================================================
# ANALYSIS ENGINE
# =============================================================================

class LogAnalyzer:
    """Analyze parsed log events"""

    def __init__(self, parser: LogParser):
        self.parser = parser
        self.daily_summaries: List[DailySummary] = []
        self.overall_summary: Optional[OverallSummary] = None

    def analyze(self):
        """Run full analysis"""
        print("\nAnalyzing logs...")

        # Group events by date
        events_by_date = self._group_events_by_date()

        # Analyze each day
        for date_str in sorted(events_by_date.keys()):
            autorate_events, steering_events, steering_actions = events_by_date[date_str]
            daily = self._analyze_day(date_str, autorate_events, steering_events, steering_actions)
            self.daily_summaries.append(daily)

        # Create overall summary
        self.overall_summary = self._create_overall_summary()

        print(f"  Analyzed {len(self.daily_summaries)} days")

    def _group_events_by_date(self) -> Dict[str, Tuple[List, List, List]]:
        """Group events by date"""
        by_date = defaultdict(lambda: ([], [], []))

        for event in self.parser.autorate_events:
            date_str = event.timestamp[:10]
            by_date[date_str][0].append(event)

        for event in self.parser.steering_events:
            date_str = event.timestamp[:10]
            by_date[date_str][1].append(event)

        for event in self.parser.steering_actions:
            date_str = event.timestamp[:10]
            by_date[date_str][2].append(event)

        return dict(by_date)

    def _analyze_day(self, date_str: str, autorate_events: List[AutorateEvent],
                     steering_events: List[SteeringEvent],
                     steering_actions: List[SteeringAction]) -> DailySummary:
        """Analyze one day"""

        # State distributions and durations
        state_dist_dl = Counter([e.state_dl for e in autorate_events])
        state_dist_ul = Counter([e.state_ul for e in autorate_events])
        state_dur_dl = self._calculate_state_durations(autorate_events, 'download')
        state_dur_ul = self._calculate_state_durations(autorate_events, 'upload')

        # RTT metrics
        rtt_deltas = [e.rtt_delta for e in autorate_events]
        rtt_baselines = [e.rtt_baseline for e in autorate_events]

        # Bandwidth metrics
        bw_dl = [e.bandwidth_dl for e in autorate_events]
        bw_ul = [e.bandwidth_ul for e in autorate_events]

        # Steering metrics
        steering_dist = Counter([e.steering_state for e in steering_events])
        steering_dur = self._calculate_steering_durations(steering_events)
        congestion_dist = Counter([e.congestion for e in steering_events])

        steering_enables = sum(1 for a in steering_actions if a.action == "enable")
        steering_disables = sum(1 for a in steering_actions if a.action == "disable")
        steering_active_duration = self._calculate_steering_active_duration(steering_actions)

        # Transitions
        dl_trans = self._find_transitions(autorate_events, 'download')
        ul_trans = self._find_transitions(autorate_events, 'upload')
        steering_trans = self._find_steering_transitions(steering_events)

        # Hourly distributions
        cycles_by_hour, soft_red_by_hour, red_by_hour, steering_by_hour = \
            self._calculate_hourly_distributions(autorate_events, steering_actions)

        return DailySummary(
            date=date_str,
            autorate_cycles=len(autorate_events),
            state_distribution_dl=dict(state_dist_dl),
            state_distribution_ul=dict(state_dist_ul),
            state_duration_dl=state_dur_dl,
            state_duration_ul=state_dur_ul,
            rtt_baseline_mean=sum(rtt_baselines) / len(rtt_baselines) if rtt_baselines else 0,
            rtt_baseline_min=min(rtt_baselines) if rtt_baselines else 0,
            rtt_baseline_max=max(rtt_baselines) if rtt_baselines else 0,
            rtt_delta_mean=sum(rtt_deltas) / len(rtt_deltas) if rtt_deltas else 0,
            rtt_delta_p50=self._percentile(rtt_deltas, 50) if rtt_deltas else 0,
            rtt_delta_p95=self._percentile(rtt_deltas, 95) if rtt_deltas else 0,
            rtt_delta_p99=self._percentile(rtt_deltas, 99) if rtt_deltas else 0,
            rtt_delta_max=max(rtt_deltas) if rtt_deltas else 0,
            bandwidth_dl_mean=int(sum(bw_dl) / len(bw_dl)) if bw_dl else 0,
            bandwidth_dl_min=min(bw_dl) if bw_dl else 0,
            bandwidth_dl_max=max(bw_dl) if bw_dl else 0,
            bandwidth_ul_mean=int(sum(bw_ul) / len(bw_ul)) if bw_ul else 0,
            bandwidth_ul_min=min(bw_ul) if bw_ul else 0,
            bandwidth_ul_max=max(bw_ul) if bw_ul else 0,
            steering_cycles=len(steering_events),
            steering_distribution=dict(steering_dist),
            steering_duration=steering_dur,
            steering_enables=steering_enables,
            steering_disables=steering_disables,
            steering_total_duration_active=steering_active_duration,
            congestion_distribution=dict(congestion_dist),
            dl_transitions=dl_trans,
            ul_transitions=ul_trans,
            steering_transitions=steering_trans,
            cycles_by_hour=cycles_by_hour,
            soft_red_by_hour=soft_red_by_hour,
            red_by_hour=red_by_hour,
            steering_active_by_hour=steering_by_hour
        )

    def _calculate_state_durations(self, events: List[AutorateEvent], direction: str) -> Dict[str, float]:
        """Calculate time spent in each state (seconds)"""
        if not events:
            return {}

        durations = defaultdict(float)
        prev_event = None

        for event in events:
            if prev_event:
                state = prev_event.state_dl if direction == 'download' else prev_event.state_ul
                duration = (self._parse_timestamp(event.timestamp) -
                           self._parse_timestamp(prev_event.timestamp)).total_seconds()
                durations[state] += duration
            prev_event = event

        return dict(durations)

    def _calculate_steering_durations(self, events: List[SteeringEvent]) -> Dict[str, float]:
        """Calculate time spent in each steering state"""
        if not events:
            return {}

        durations = defaultdict(float)
        prev_event = None

        for event in events:
            if prev_event:
                duration = (self._parse_timestamp(event.timestamp) -
                           self._parse_timestamp(prev_event.timestamp)).total_seconds()
                durations[prev_event.steering_state] += duration
            prev_event = event

        return dict(durations)

    def _calculate_steering_active_duration(self, actions: List[SteeringAction]) -> float:
        """Calculate total time steering was active"""
        if not actions:
            return 0.0

        total_duration = 0.0
        last_enable = None

        for action in sorted(actions, key=lambda a: a.timestamp):
            if action.action == "enable":
                last_enable = self._parse_timestamp(action.timestamp)
            elif action.action == "disable" and last_enable:
                duration = (self._parse_timestamp(action.timestamp) - last_enable).total_seconds()
                total_duration += duration
                last_enable = None

        return total_duration

    def _find_transitions(self, events: List[AutorateEvent], direction: str) -> List[str]:
        """Find state transitions"""
        transitions = []
        prev_state = None
        prev_timestamp = None

        for event in events:
            current_state = event.state_dl if direction == 'download' else event.state_ul

            if prev_state and current_state != prev_state:
                transitions.append(
                    f"{prev_state}→{current_state} at {event.timestamp}"
                )

            prev_state = current_state
            prev_timestamp = event.timestamp

        return transitions

    def _find_steering_transitions(self, events: List[SteeringEvent]) -> List[str]:
        """Find steering state transitions"""
        transitions = []
        prev_state = None

        for event in events:
            if prev_state and event.steering_state != prev_state:
                transitions.append(
                    f"{prev_state}→{event.steering_state} at {event.timestamp}"
                )
            prev_state = event.steering_state

        return transitions

    def _calculate_hourly_distributions(self, autorate_events: List[AutorateEvent],
                                       steering_actions: List[SteeringAction]) -> Tuple:
        """Calculate per-hour distributions"""
        cycles_by_hour = defaultdict(int)
        soft_red_by_hour = defaultdict(int)
        red_by_hour = defaultdict(int)
        steering_by_hour = defaultdict(int)

        for event in autorate_events:
            hour = int(event.timestamp[11:13])
            cycles_by_hour[hour] += 1
            if event.state_dl == "SOFT_RED":
                soft_red_by_hour[hour] += 1
            if event.state_dl == "RED":
                red_by_hour[hour] += 1

        # Calculate steering active time per hour
        steering_active = set()
        last_enable = None

        for action in sorted(steering_actions, key=lambda a: a.timestamp):
            if action.action == "enable":
                last_enable = self._parse_timestamp(action.timestamp)
            elif action.action == "disable" and last_enable:
                # Mark all hours between enable and disable as active
                current = last_enable
                end = self._parse_timestamp(action.timestamp)
                while current <= end:
                    steering_active.add(current.hour)
                    current += timedelta(hours=1)
                last_enable = None

        for hour in steering_active:
            steering_by_hour[hour] += 1

        return dict(cycles_by_hour), dict(soft_red_by_hour), dict(red_by_hour), dict(steering_by_hour)

    def _create_overall_summary(self) -> OverallSummary:
        """Create overall summary from daily summaries"""
        if not self.daily_summaries:
            return None

        # Aggregate state distributions
        state_dist_dl = Counter()
        state_dist_ul = Counter()
        state_dur_dl = defaultdict(float)
        state_dur_ul = defaultdict(float)
        steering_dist = Counter()
        steering_dur = defaultdict(float)
        congestion_dist = Counter()

        total_cycles = 0
        total_steering_cycles = 0
        total_steering_enables = 0
        total_steering_disables = 0
        total_steering_active = 0.0

        all_rtt_deltas = []
        all_rtt_baselines = []

        dl_transition_counts = Counter()
        ul_transition_counts = Counter()
        steering_transition_counts = Counter()

        for daily in self.daily_summaries:
            total_cycles += daily.autorate_cycles
            total_steering_cycles += daily.steering_cycles
            total_steering_enables += daily.steering_enables
            total_steering_disables += daily.steering_disables
            total_steering_active += daily.steering_total_duration_active

            for state, count in daily.state_distribution_dl.items():
                state_dist_dl[state] += count
            for state, count in daily.state_distribution_ul.items():
                state_dist_ul[state] += count
            for state, dur in daily.state_duration_dl.items():
                state_dur_dl[state] += dur
            for state, dur in daily.state_duration_ul.items():
                state_dur_ul[state] += dur
            for state, count in daily.steering_distribution.items():
                steering_dist[state] += count
            for state, dur in daily.steering_duration.items():
                steering_dur[state] += dur
            for state, count in daily.congestion_distribution.items():
                congestion_dist[state] += count

            # Count transitions
            for trans in daily.dl_transitions:
                transition_type = trans.split(' at ')[0]
                dl_transition_counts[transition_type] += 1
            for trans in daily.ul_transitions:
                transition_type = trans.split(' at ')[0]
                ul_transition_counts[transition_type] += 1
            for trans in daily.steering_transitions:
                transition_type = trans.split(' at ')[0]
                steering_transition_counts[transition_type] += 1

        # Collect all RTT deltas for percentiles (approximation from daily means)
        # Note: This is an approximation. For exact percentiles, we'd need all raw data.
        for daily in self.daily_summaries:
            all_rtt_deltas.append(daily.rtt_delta_mean)
            all_rtt_baselines.append(daily.rtt_baseline_mean)

        return OverallSummary(
            start_date=self.daily_summaries[0].date,
            end_date=self.daily_summaries[-1].date,
            total_days=len(self.daily_summaries),
            total_cycles=total_cycles,
            state_distribution_dl=dict(state_dist_dl),
            state_distribution_ul=dict(state_dist_ul),
            state_duration_dl=dict(state_dur_dl),
            state_duration_ul=dict(state_dur_ul),
            rtt_baseline_overall_mean=sum(all_rtt_baselines) / len(all_rtt_baselines) if all_rtt_baselines else 0,
            rtt_delta_overall_mean=sum(all_rtt_deltas) / len(all_rtt_deltas) if all_rtt_deltas else 0,
            rtt_delta_overall_p95=self._percentile(all_rtt_deltas, 95) if all_rtt_deltas else 0,
            rtt_delta_overall_p99=self._percentile(all_rtt_deltas, 99) if all_rtt_deltas else 0,
            rtt_delta_overall_max=max(all_rtt_deltas) if all_rtt_deltas else 0,
            total_steering_cycles=total_steering_cycles,
            steering_distribution=dict(steering_dist),
            steering_duration=dict(steering_dur),
            total_steering_enables=total_steering_enables,
            total_steering_disables=total_steering_disables,
            steering_total_duration_active=total_steering_active,
            congestion_distribution=dict(congestion_dist),
            dl_transition_counts=dict(dl_transition_counts),
            ul_transition_counts=dict(ul_transition_counts),
            steering_transition_counts=dict(steering_transition_counts),
            daily_summaries=self.daily_summaries
        )

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse timestamp string to datetime"""
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')

    @staticmethod
    def _percentile(data: List[float], pct: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * pct / 100.0)
        return sorted_data[min(index, len(sorted_data) - 1)]


# =============================================================================
# OUTPUT GENERATION
# =============================================================================

class OutputGenerator:
    """Generate CSV and JSON outputs"""

    def __init__(self, analyzer: LogAnalyzer, output_dir: Path):
        self.analyzer = analyzer
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self):
        """Generate all output files"""
        print(f"\nGenerating outputs to {self.output_dir}/")

        self._generate_daily_summary_csv()
        self._generate_overall_summary_json()
        self._generate_transitions_csv()
        self._generate_hourly_distributions_csv()
        self._generate_steering_events_csv()

        print("  Done!")

    def _generate_daily_summary_csv(self):
        """Generate daily summary CSV"""
        output_path = self.output_dir / "daily_summary.csv"

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Date',
                'Cycles',
                'GREEN_DL_%', 'YELLOW_DL_%', 'SOFT_RED_DL_%', 'RED_DL_%',
                'GREEN_UL_%', 'YELLOW_UL_%', 'RED_UL_%',
                'RTT_Baseline_Mean', 'RTT_Delta_Mean', 'RTT_Delta_P95', 'RTT_Delta_Max',
                'BW_DL_Mean', 'BW_DL_Min', 'BW_DL_Max',
                'BW_UL_Mean', 'BW_UL_Min', 'BW_UL_Max',
                'Steering_Enables', 'Steering_Disables', 'Steering_Active_Seconds',
                'DL_Transitions', 'UL_Transitions', 'Steering_Transitions'
            ])

            # Data rows
            for daily in self.analyzer.daily_summaries:
                total_dl = sum(daily.state_distribution_dl.values())
                total_ul = sum(daily.state_distribution_ul.values())

                writer.writerow([
                    daily.date,
                    daily.autorate_cycles,
                    f"{daily.state_distribution_dl.get('GREEN', 0) / total_dl * 100:.1f}" if total_dl else "0",
                    f"{daily.state_distribution_dl.get('YELLOW', 0) / total_dl * 100:.1f}" if total_dl else "0",
                    f"{daily.state_distribution_dl.get('SOFT_RED', 0) / total_dl * 100:.1f}" if total_dl else "0",
                    f"{daily.state_distribution_dl.get('RED', 0) / total_dl * 100:.1f}" if total_dl else "0",
                    f"{daily.state_distribution_ul.get('GREEN', 0) / total_ul * 100:.1f}" if total_ul else "0",
                    f"{daily.state_distribution_ul.get('YELLOW', 0) / total_ul * 100:.1f}" if total_ul else "0",
                    f"{daily.state_distribution_ul.get('RED', 0) / total_ul * 100:.1f}" if total_ul else "0",
                    f"{daily.rtt_baseline_mean:.2f}",
                    f"{daily.rtt_delta_mean:.2f}",
                    f"{daily.rtt_delta_p95:.2f}",
                    f"{daily.rtt_delta_max:.2f}",
                    daily.bandwidth_dl_mean,
                    daily.bandwidth_dl_min,
                    daily.bandwidth_dl_max,
                    daily.bandwidth_ul_mean,
                    daily.bandwidth_ul_min,
                    daily.bandwidth_ul_max,
                    daily.steering_enables,
                    daily.steering_disables,
                    f"{daily.steering_total_duration_active:.1f}",
                    len(daily.dl_transitions),
                    len(daily.ul_transitions),
                    len(daily.steering_transitions)
                ])

        print(f"  Wrote {output_path}")

    def _generate_overall_summary_json(self):
        """Generate overall summary JSON"""
        output_path = self.output_dir / "overall_summary.json"

        if not self.analyzer.overall_summary:
            print("  No overall summary to write")
            return

        # Convert to dict, excluding daily_summaries (too large)
        summary_dict = asdict(self.analyzer.overall_summary)
        summary_dict.pop('daily_summaries', None)

        with open(output_path, 'w') as f:
            json.dump(summary_dict, f, indent=2)

        print(f"  Wrote {output_path}")

    def _generate_transitions_csv(self):
        """Generate transitions CSV"""
        output_path = self.output_dir / "transitions.csv"

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Direction', 'Transition'])

            for daily in self.analyzer.daily_summaries:
                for trans in daily.dl_transitions:
                    writer.writerow([daily.date, 'Download', trans])
                for trans in daily.ul_transitions:
                    writer.writerow([daily.date, 'Upload', trans])
                for trans in daily.steering_transitions:
                    writer.writerow([daily.date, 'Steering', trans])

        print(f"  Wrote {output_path}")

    def _generate_hourly_distributions_csv(self):
        """Generate hourly distributions CSV"""
        output_path = self.output_dir / "hourly_distributions.csv"

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Hour', 'Total_Cycles', 'SOFT_RED_Count', 'RED_Count', 'Steering_Active'])

            for daily in self.analyzer.daily_summaries:
                for hour in range(24):
                    writer.writerow([
                        daily.date,
                        hour,
                        daily.cycles_by_hour.get(hour, 0),
                        daily.soft_red_by_hour.get(hour, 0),
                        daily.red_by_hour.get(hour, 0),
                        daily.steering_active_by_hour.get(hour, 0)
                    ])

        print(f"  Wrote {output_path}")

    def _generate_steering_events_csv(self):
        """Generate steering events CSV"""
        output_path = self.output_dir / "steering_events.csv"

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Action'])

            for action in sorted(self.analyzer.parser.steering_actions, key=lambda a: a.timestamp):
                writer.writerow([action.timestamp, action.action])

        print(f"  Wrote {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Analyze CAKE autorate and steering logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze logs from remote container (default)
  python analyze_logs.py

  # Analyze local log files
  python analyze_logs.py --autorate /path/to/cake_auto.log --steering /path/to/steering.log

  # Custom output directory
  python analyze_logs.py --output /path/to/analysis/
        """
    )

    parser.add_argument('--autorate', type=Path,
                       help='Path to autorate log file (default: fetch from container)')
    parser.add_argument('--steering', type=Path,
                       help='Path to steering log file (default: fetch from container)')
    parser.add_argument('--output', type=Path, default=Path('./analysis'),
                       help='Output directory for analysis files (default: ./analysis)')
    parser.add_argument('--remote-host', default='kevin@10.10.110.246',
                       help='Remote host for fetching logs (default: kevin@10.10.110.246)')
    parser.add_argument('--ssh-key', type=Path, default=Path.home() / '.ssh' / 'mikrotik_cake',
                       help='SSH key for remote host (default: ~/.ssh/mikrotik_cake)')

    args = parser.parse_args()

    # Determine log paths
    if args.autorate and args.steering:
        autorate_log = args.autorate
        steering_log = args.steering
    else:
        print(f"Fetching logs from {args.remote_host}...")
        print("(This may take a moment for large logs)")

        # Fetch logs from remote container
        import subprocess
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix='cake_logs_'))
        autorate_log = temp_dir / 'cake_auto.log'
        steering_log = temp_dir / 'steering.log'

        try:
            # Copy autorate log
            subprocess.run([
                'scp', '-i', str(args.ssh_key),
                f'{args.remote_host}:/home/kevin/wanctl/logs/cake_auto.log',
                str(autorate_log)
            ], check=True, capture_output=True)

            # Copy steering log
            subprocess.run([
                'scp', '-i', str(args.ssh_key),
                f'{args.remote_host}:/home/kevin/wanctl/logs/steering.log',
                str(steering_log)
            ], check=True, capture_output=True)

            print(f"  Downloaded to {temp_dir}/")
        except subprocess.CalledProcessError as e:
            print(f"Error fetching logs: {e}", file=sys.stderr)
            sys.exit(1)

    # Parse logs
    log_parser = LogParser()
    log_parser.parse_autorate_log(autorate_log)
    log_parser.parse_steering_log(steering_log)

    if not log_parser.autorate_events and not log_parser.steering_events:
        print("No events found in logs!", file=sys.stderr)
        sys.exit(1)

    # Analyze
    analyzer = LogAnalyzer(log_parser)
    analyzer.analyze()

    # Generate outputs
    output_gen = OutputGenerator(analyzer, args.output)
    output_gen.generate_all()

    # Print summary
    if analyzer.overall_summary:
        print(f"\n=== Overall Summary ===")
        print(f"Period: {analyzer.overall_summary.start_date} to {analyzer.overall_summary.end_date}")
        print(f"Total days: {analyzer.overall_summary.total_days}")
        print(f"Total cycles: {analyzer.overall_summary.total_cycles:,}")
        print(f"\nDownload state distribution:")
        total_dl = sum(analyzer.overall_summary.state_distribution_dl.values())
        for state in ['GREEN', 'YELLOW', 'SOFT_RED', 'RED']:
            count = analyzer.overall_summary.state_distribution_dl.get(state, 0)
            pct = count / total_dl * 100 if total_dl else 0
            print(f"  {state:10s}: {pct:5.1f}% ({count:,} cycles)")

        print(f"\nSteering summary:")
        print(f"  Enables:  {analyzer.overall_summary.total_steering_enables}")
        print(f"  Disables: {analyzer.overall_summary.total_steering_disables}")
        print(f"  Active time: {analyzer.overall_summary.steering_total_duration_active / 3600:.1f} hours")


if __name__ == '__main__':
    main()
