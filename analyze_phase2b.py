#!/usr/bin/env python3
"""
Phase 2B Dry-Run Analysis
Compares Phase 2B hypothetical steering with Phase 2A actual steering
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import csv

@dataclass
class SteeringEvent:
    """Represents a steering event (Phase 2A actual or Phase 2B hypothetical)"""
    timestamp: datetime
    event_type: str  # ENABLE, DISABLE, WOULD_ENABLE, WOULD_DISABLE
    phase: str  # 2A or 2B
    rtt_delta: Optional[float] = None
    drops: Optional[int] = None
    queue_depth: Optional[int] = None
    cake_state: Optional[str] = None
    confidence: Optional[float] = None
    signals: List[str] = field(default_factory=list)

@dataclass
class ConfidencePoint:
    """Confidence measurement at a point in time"""
    timestamp: datetime
    confidence: float
    signals: List[str]
    cake_state: str

class Phase2BAnalyzer:
    """Analyze Phase 2B dry-run vs Phase 2A actual steering"""

    def __init__(self, log_path: str, days: int = 7):
        self.log_path = Path(log_path)
        self.days = days
        self.cutoff_date = datetime.now() - timedelta(days=days)

        # Data structures
        self.phase2a_events: List[SteeringEvent] = []
        self.phase2b_events: List[SteeringEvent] = []
        self.confidence_history: List[ConfidencePoint] = []
        self.all_assessments: List[Dict] = []

        # Statistics
        self.phase2a_enables = 0
        self.phase2a_disables = 0
        self.phase2b_would_enables = 0
        self.phase2b_would_disables = 0
        self.flap_brake_events = 0

    def parse_logs(self):
        """Parse steering logs and extract events"""
        print(f"Parsing {self.log_path.name}...")
        print(f"Filtering to past {self.days} days (since {self.cutoff_date.strftime('%Y-%m-%d')})")

        current_assessment = {}
        line_count = 0

        with open(self.log_path, 'r') as f:
            for line in f:
                line_count += 1
                if line_count % 100000 == 0:
                    print(f"  Processed {line_count//1000}K lines...")

                # Extract timestamp
                ts_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not ts_match:
                    continue

                ts = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S')
                if ts < self.cutoff_date:
                    continue

                # Parse Phase 2A actual steering events
                if 'ENABLE_STEERING' in line and '[Steering]' in line:
                    event = self._parse_phase2a_event(line, ts, 'ENABLE')
                    if event:
                        self.phase2a_events.append(event)
                        self.phase2a_enables += 1

                elif 'DISABLE_STEERING' in line and '[Steering]' in line:
                    event = self._parse_phase2a_event(line, ts, 'DISABLE')
                    if event:
                        self.phase2a_events.append(event)
                        self.phase2a_disables += 1

                # Parse Phase 2B hypothetical steering events
                elif '[PHASE2B]' in line:
                    if 'WOULD_ENABLE_STEERING' in line:
                        event = self._parse_phase2b_event(line, ts, 'WOULD_ENABLE', current_assessment)
                        if event:
                            self.phase2b_events.append(event)
                            self.phase2b_would_enables += 1

                    elif 'WOULD_DISABLE_STEERING' in line:
                        event = self._parse_phase2b_event(line, ts, 'WOULD_DISABLE', current_assessment)
                        if event:
                            self.phase2b_events.append(event)
                            self.phase2b_would_disables += 1

                    elif 'confidence=' in line:
                        # Extract confidence and signals
                        self._parse_confidence(line, ts, current_assessment)

                # Parse congestion assessments (for context)
                if 'rtt=' in line and 'drops=' in line and 'q=' in line:
                    self._parse_assessment(line, ts, current_assessment)

                # Track flap brake
                if 'flap-brake' in line.lower() or 'FLAP_BRAKE' in line:
                    self.flap_brake_events += 1

        print(f"✓ Parsed {line_count} lines")
        print(f"✓ Phase 2A: {self.phase2a_enables} enables, {self.phase2a_disables} disables")
        print(f"✓ Phase 2B: {self.phase2b_would_enables} hypothetical enables, {self.phase2b_would_disables} hypothetical disables")
        print(f"✓ Flap brake events: {self.flap_brake_events}")

    def _parse_phase2a_event(self, line: str, ts: datetime, event_type: str) -> Optional[SteeringEvent]:
        """Parse Phase 2A actual steering event"""
        event = SteeringEvent(timestamp=ts, event_type=event_type, phase='2A')

        # Try to extract context from line
        rtt_match = re.search(r'rtt=([\d.]+)ms', line)
        if rtt_match:
            event.rtt_delta = float(rtt_match.group(1))

        drops_match = re.search(r'drops=(\d+)', line)
        if drops_match:
            event.drops = int(drops_match.group(1))

        queue_match = re.search(r'q=(\d+)', line)
        if queue_match:
            event.queue_depth = int(queue_match.group(1))

        state_match = re.search(r'congestion=(GREEN|YELLOW|RED)', line)
        if state_match:
            event.cake_state = state_match.group(1)

        return event

    def _parse_phase2b_event(self, line: str, ts: datetime, event_type: str, current_assessment: Dict) -> Optional[SteeringEvent]:
        """Parse Phase 2B hypothetical steering event"""
        event = SteeringEvent(timestamp=ts, event_type=event_type, phase='2B')

        # Extract confidence
        conf_match = re.search(r'confidence=([\d.]+)', line)
        if conf_match:
            event.confidence = float(conf_match.group(1))

        # Extract signals
        signals = []
        if 'RED' in line:
            signals.append('CAKE_RED')
        if 'rtt_high' in line or 'RTT' in line:
            signals.append('RTT_HIGH')
        if 'drops' in line:
            signals.append('DROPS')
        if 'queue' in line:
            signals.append('QUEUE_HIGH')

        event.signals = signals

        # Get context from current assessment
        event.rtt_delta = current_assessment.get('rtt_delta')
        event.drops = current_assessment.get('drops')
        event.queue_depth = current_assessment.get('queue')
        event.cake_state = current_assessment.get('cake_state')

        return event

    def _parse_confidence(self, line: str, ts: datetime, current_assessment: Dict):
        """Parse confidence level and signals"""
        conf_match = re.search(r'confidence=([\d.]+)', line)
        if conf_match:
            confidence = float(conf_match.group(1))

            signals = []
            if 'RED' in line:
                signals.append('CAKE_RED')
            if 'rtt' in line.lower():
                signals.append('RTT_HIGH')
            if 'drop' in line.lower():
                signals.append('DROPS')
            if 'queue' in line.lower():
                signals.append('QUEUE_HIGH')

            cake_state = current_assessment.get('cake_state', 'UNKNOWN')

            cp = ConfidencePoint(
                timestamp=ts,
                confidence=confidence,
                signals=signals,
                cake_state=cake_state
            )
            self.confidence_history.append(cp)

    def _parse_assessment(self, line: str, ts: datetime, current_assessment: Dict):
        """Parse congestion assessment line for context"""
        rtt_match = re.search(r'rtt=([\d.]+)ms', line)
        if rtt_match:
            current_assessment['rtt_delta'] = float(rtt_match.group(1))

        drops_match = re.search(r'drops=(\d+)', line)
        if drops_match:
            current_assessment['drops'] = int(drops_match.group(1))

        queue_match = re.search(r'q=(\d+)', line)
        if queue_match:
            current_assessment['queue'] = int(queue_match.group(1))

        state_match = re.search(r'congestion=(GREEN|YELLOW|RED)', line)
        if state_match:
            current_assessment['cake_state'] = state_match.group(1)

        # Store full assessment
        if all(k in current_assessment for k in ['rtt_delta', 'drops', 'queue', 'cake_state']):
            self.all_assessments.append({
                'timestamp': ts,
                **current_assessment
            })

    def analyze_comparative_behavior(self):
        """Compare Phase 2A actual vs Phase 2B hypothetical steering"""
        print("\n" + "="*60)
        print("COMPARATIVE BEHAVIOR ANALYSIS")
        print("="*60)

        results = []

        # For each Phase 2A enable, check if Phase 2B would have enabled
        print("\nPhase 2A Enable Events vs Phase 2B:")
        for p2a in [e for e in self.phase2a_events if e.event_type == 'ENABLE']:
            # Find Phase 2B events within ±2 minutes
            window_start = p2a.timestamp - timedelta(minutes=2)
            window_end = p2a.timestamp + timedelta(minutes=2)

            p2b_matches = [
                e for e in self.phase2b_events
                if e.event_type == 'WOULD_ENABLE' and window_start <= e.timestamp <= window_end
            ]

            if p2b_matches:
                # Phase 2B would have steered too
                first_match = min(p2b_matches, key=lambda e: e.timestamp)
                time_diff = (first_match.timestamp - p2a.timestamp).total_seconds()

                result = {
                    'p2a_time': p2a.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'p2b_agreement': 'YES',
                    'p2b_time_diff_sec': time_diff,
                    'p2b_confidence': first_match.confidence,
                    'p2a_cake_state': p2a.cake_state,
                    'p2b_signals': ','.join(first_match.signals)
                }
            else:
                # Phase 2B would NOT have steered
                result = {
                    'p2a_time': p2a.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'p2b_agreement': 'NO',
                    'p2b_time_diff_sec': None,
                    'p2b_confidence': None,
                    'p2a_cake_state': p2a.cake_state,
                    'p2b_signals': None
                }

            results.append(result)
            print(f"  {result['p2a_time']}: P2B={result['p2b_agreement']}, "
                  f"CAKE={result['p2a_cake_state']}, "
                  f"confidence={result['p2b_confidence']}, "
                  f"lag={result['p2b_time_diff_sec']}s")

        return results

    def analyze_confidence_dynamics(self):
        """Analyze confidence ramp-up and decay behavior"""
        print("\n" + "="*60)
        print("CONFIDENCE DYNAMICS ANALYSIS")
        print("="*60)

        if not self.confidence_history:
            print("No confidence data found!")
            return {}

        confidences = [cp.confidence for cp in self.confidence_history]

        stats = {
            'mean': sum(confidences) / len(confidences),
            'max': max(confidences),
            'min': min(confidences),
            'p95': sorted(confidences)[int(len(confidences) * 0.95)],
            'above_70': sum(1 for c in confidences if c >= 70),
            'above_50': sum(1 for c in confidences if c >= 50),
            'total_samples': len(confidences)
        }

        print(f"\nConfidence Statistics:")
        print(f"  Mean: {stats['mean']:.1f}")
        print(f"  Max: {stats['max']:.1f}")
        print(f"  Min: {stats['min']:.1f}")
        print(f"  P95: {stats['p95']:.1f}")
        print(f"  Samples ≥70 (threshold): {stats['above_70']} ({100*stats['above_70']/stats['total_samples']:.2f}%)")
        print(f"  Samples ≥50: {stats['above_50']} ({100*stats['above_50']/stats['total_samples']:.2f}%)")

        # Analyze ramp-up times (time to reach 70)
        ramp_times = []
        current_ramp_start = None

        for i, cp in enumerate(self.confidence_history):
            if cp.confidence >= 10 and current_ramp_start is None:
                current_ramp_start = i
            elif cp.confidence >= 70 and current_ramp_start is not None:
                # Calculate ramp time
                start_ts = self.confidence_history[current_ramp_start].timestamp
                end_ts = cp.timestamp
                ramp_time = (end_ts - start_ts).total_seconds()
                ramp_times.append(ramp_time)
                current_ramp_start = None
            elif cp.confidence < 10:
                current_ramp_start = None

        if ramp_times:
            print(f"\nRamp-up Times (0→70):")
            print(f"  Mean: {sum(ramp_times)/len(ramp_times):.1f}s")
            print(f"  Min: {min(ramp_times):.1f}s")
            print(f"  Max: {max(ramp_times):.1f}s")
            print(f"  Count: {len(ramp_times)} ramps observed")

        return stats

    def analyze_false_positives_misses(self):
        """Identify Phase 2B false positives and missed events"""
        print("\n" + "="*60)
        print("FALSE POSITIVE / MISSED EVENT ANALYSIS")
        print("="*60)

        false_positives = []
        misses = []

        # False positives: Phase 2B would enable, but Phase 2A never did (within 5 min)
        for p2b in [e for e in self.phase2b_events if e.event_type == 'WOULD_ENABLE']:
            window_start = p2b.timestamp - timedelta(minutes=5)
            window_end = p2b.timestamp + timedelta(minutes=5)

            p2a_match = any(
                e.event_type == 'ENABLE' and window_start <= e.timestamp <= window_end
                for e in self.phase2a_events
            )

            if not p2a_match:
                false_positives.append(p2b)

        # Misses: Phase 2A enabled, but Phase 2B didn't want to (within 2 min)
        for p2a in [e for e in self.phase2a_events if e.event_type == 'ENABLE']:
            window_start = p2a.timestamp - timedelta(minutes=2)
            window_end = p2a.timestamp + timedelta(minutes=2)

            p2b_match = any(
                e.event_type == 'WOULD_ENABLE' and window_start <= e.timestamp <= window_end
                for e in self.phase2b_events
            )

            if not p2b_match:
                misses.append(p2a)

        print(f"\nFalse Positives (P2B would steer, P2A didn't):")
        print(f"  Count: {len(false_positives)}")
        if false_positives:
            for fp in false_positives[:5]:  # Show first 5
                print(f"    {fp.timestamp.strftime('%Y-%m-%d %H:%M:%S')}: "
                      f"confidence={fp.confidence}, CAKE={fp.cake_state}, signals={fp.signals}")

        print(f"\nMissed Events (P2A steered, P2B wouldn't):")
        print(f"  Count: {len(misses)}")
        if misses:
            for miss in misses[:5]:  # Show first 5
                print(f"    {miss.timestamp.strftime('%Y-%m-%d %H:%M:%S')}: "
                      f"CAKE={miss.cake_state}, rtt={miss.rtt_delta}ms, drops={miss.drops}")

        return {
            'false_positives': len(false_positives),
            'misses': len(misses),
            'fp_events': false_positives,
            'miss_events': misses
        }

    def generate_event_inventory(self):
        """Generate summary table of all events"""
        print("\n" + "="*60)
        print("EVENT INVENTORY")
        print("="*60)

        inventory = {
            'Phase 2A Actual Steering': {
                'ENABLE_STEERING': self.phase2a_enables,
                'DISABLE_STEERING': self.phase2a_disables,
            },
            'Phase 2B Hypothetical Steering': {
                'WOULD_ENABLE_STEERING': self.phase2b_would_enables,
                'WOULD_DISABLE_STEERING': self.phase2b_would_disables,
            },
            'Other Events': {
                'Flap-brake engagements': self.flap_brake_events,
            }
        }

        for category, events in inventory.items():
            print(f"\n{category}:")
            for event, count in events.items():
                print(f"  {event}: {count}")

        return inventory

    def export_csv(self, output_path: str):
        """Export Phase 2B events to CSV"""
        print(f"\nExporting Phase 2B events to {output_path}...")

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'event_type', 'confidence', 'cake_state',
                'rtt_delta_ms', 'drops', 'queue_depth', 'signals',
                'p2a_match', 'p2a_time_diff_sec'
            ])
            writer.writeheader()

            for p2b in self.phase2b_events:
                # Find matching Phase 2A event
                window_start = p2b.timestamp - timedelta(minutes=2)
                window_end = p2b.timestamp + timedelta(minutes=2)

                p2a_matches = [
                    e for e in self.phase2a_events
                    if e.event_type.replace('WOULD_', '') == p2b.event_type.replace('WOULD_', '')
                    and window_start <= e.timestamp <= window_end
                ]

                p2a_match = 'YES' if p2a_matches else 'NO'
                p2a_time_diff = None
                if p2a_matches:
                    first_match = min(p2a_matches, key=lambda e: e.timestamp)
                    p2a_time_diff = (p2b.timestamp - first_match.timestamp).total_seconds()

                writer.writerow({
                    'timestamp': p2b.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_type': p2b.event_type,
                    'confidence': p2b.confidence,
                    'cake_state': p2b.cake_state,
                    'rtt_delta_ms': p2b.rtt_delta,
                    'drops': p2b.drops,
                    'queue_depth': p2b.queue_depth,
                    'signals': ','.join(p2b.signals) if p2b.signals else '',
                    'p2a_match': p2a_match,
                    'p2a_time_diff_sec': p2a_time_diff
                })

        print(f"✓ Exported {len(self.phase2b_events)} Phase 2B events")

def main():
    analyzer = Phase2BAnalyzer('analysis_logs/steering.log', days=7)

    # Parse logs
    analyzer.parse_logs()

    # Generate event inventory
    inventory = analyzer.generate_event_inventory()

    # Comparative behavior analysis
    comparative_results = analyzer.analyze_comparative_behavior()

    # Confidence dynamics
    confidence_stats = analyzer.analyze_confidence_dynamics()

    # False positives and misses
    fp_miss_analysis = analyzer.analyze_false_positives_misses()

    # Export CSV
    analyzer.export_csv('analysis_logs/phase2b_events.csv')

    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)
    print("\nOutputs:")
    print("  • CSV: analysis_logs/phase2b_events.csv")
    print("  • Report: docs/PHASE_2B_WEEK1_ANALYSIS.md (next step)")

if __name__ == '__main__':
    main()
