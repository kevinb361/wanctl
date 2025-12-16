#!/usr/bin/env python3
"""
CAKE Congestion Pattern Analyzer

Parses continuous monitor logs to:
1. Identify hourly congestion patterns
2. Recommend state-based floors (GREEN/YELLOW/RED)
3. Generate time-of-day bias recommendations
4. Visualize congestion timeline

Expert guidance: https://chatgpt.com/share/...
"""

import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import statistics


class CongestionAnalyzer:
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.samples = []
        self.hourly_stats = defaultdict(lambda: {
            'samples': 0,
            'green': 0,
            'yellow': 0,
            'red': 0,
            'deltas': [],
            'rtts': [],
            'dl_rates': [],
            'ul_rates': []
        })

    def parse_logs(self):
        """Parse continuous monitor log entries"""
        # Pattern: 2025-12-13 08:00:22,775 [Spectrum] [INFO] Spectrum: [RED/RED] RTT=46.9ms, load_ewma=47.6ms, baseline=25.0ms, delta=22.5ms | DL=491M, UL=25M
        pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[(\w+)\] \[INFO\] \w+: \[(\w+)/(\w+)\] RTT=([\d.]+)ms, load_ewma=([\d.]+)ms, baseline=([\d.]+)ms, delta=([-\d.]+)ms \| DL=(\d+)M, UL=(\d+)M'
        )

        print(f"Parsing {self.log_file}...")

        with open(self.log_file, 'r') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    timestamp_str, wan, dl_state, ul_state, rtt, load_ewma, baseline, delta, dl_rate, ul_rate = match.groups()

                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    hour = timestamp.hour

                    sample = {
                        'timestamp': timestamp,
                        'hour': hour,
                        'wan': wan,
                        'dl_state': dl_state,
                        'ul_state': ul_state,
                        'rtt': float(rtt),
                        'load_ewma': float(load_ewma),
                        'baseline': float(baseline),
                        'delta': float(delta),
                        'dl_rate': int(dl_rate),
                        'ul_rate': int(ul_rate)
                    }

                    self.samples.append(sample)

                    # Aggregate hourly
                    stats = self.hourly_stats[hour]
                    stats['samples'] += 1
                    stats['deltas'].append(sample['delta'])
                    stats['rtts'].append(sample['rtt'])
                    stats['dl_rates'].append(sample['dl_rate'])
                    stats['ul_rates'].append(sample['ul_rate'])

                    if dl_state == 'GREEN':
                        stats['green'] += 1
                    elif dl_state == 'YELLOW':
                        stats['yellow'] += 1
                    elif dl_state == 'RED':
                        stats['red'] += 1

        print(f"Parsed {len(self.samples)} samples across {len(self.hourly_stats)} hours\n")

    def analyze_hourly_patterns(self):
        """Generate hourly congestion statistics"""
        print("=" * 80)
        print("HOURLY CONGESTION ANALYSIS")
        print("=" * 80)
        print(f"{'Hour':<6} {'Samples':<8} {'Green%':<8} {'Yellow%':<9} {'Red%':<7} {'Median Δ':<10} {'p95 Δ':<10} {'Median DL'}")
        print("-" * 80)

        for hour in sorted(self.hourly_stats.keys()):
            stats = self.hourly_stats[hour]
            total = stats['samples']

            if total == 0:
                continue

            green_pct = (stats['green'] / total) * 100
            yellow_pct = (stats['yellow'] / total) * 100
            red_pct = (stats['red'] / total) * 100

            median_delta = statistics.median(stats['deltas'])
            p95_delta = statistics.quantiles(stats['deltas'], n=20)[18] if len(stats['deltas']) > 20 else max(stats['deltas'])
            median_dl = statistics.median(stats['dl_rates'])

            print(f"{hour:02d}:00  {total:<8} {green_pct:>6.1f}%  {yellow_pct:>7.1f}%  {red_pct:>5.1f}%  {median_delta:>7.1f}ms  {p95_delta:>7.1f}ms  {median_dl:>6.0f}M")

        print()

    def recommend_floors(self, wan_name: str, current_ceiling: int):
        """Recommend state-based floors based on expert guidance"""
        print("=" * 80)
        print(f"STATE-BASED FLOOR RECOMMENDATIONS - {wan_name}")
        print("=" * 80)

        # Analyze overall distribution
        all_deltas = []
        all_dl_rates = []
        all_states = {'GREEN': 0, 'YELLOW': 0, 'RED': 0}

        for sample in self.samples:
            all_deltas.append(sample['delta'])
            all_dl_rates.append(sample['dl_rate'])
            all_states[sample['dl_state']] += 1

        total_samples = len(self.samples)
        green_pct = (all_states['GREEN'] / total_samples) * 100
        yellow_pct = (all_states['YELLOW'] / total_samples) * 100
        red_pct = (all_states['RED'] / total_samples) * 100

        print(f"\nOverall State Distribution:")
        print(f"  GREEN:  {green_pct:>5.1f}% ({all_states['GREEN']} samples)")
        print(f"  YELLOW: {yellow_pct:>5.1f}% ({all_states['YELLOW']} samples)")
        print(f"  RED:    {red_pct:>5.1f}% ({all_states['RED']} samples)")

        # Calculate percentiles of DL rates in each state
        green_rates = [s['dl_rate'] for s in self.samples if s['dl_state'] == 'GREEN']
        yellow_rates = [s['dl_rate'] for s in self.samples if s['dl_state'] == 'YELLOW']
        red_rates = [s['dl_rate'] for s in self.samples if s['dl_state'] == 'RED']

        print(f"\nObserved Rate Ranges:")
        if green_rates:
            print(f"  GREEN:  median={statistics.median(green_rates):.0f}M, p10={statistics.quantiles(green_rates, n=10)[0]:.0f}M")
        if yellow_rates:
            print(f"  YELLOW: median={statistics.median(yellow_rates):.0f}M, p10={statistics.quantiles(yellow_rates, n=10)[0]:.0f}M")
        if red_rates:
            print(f"  RED:    median={statistics.median(red_rates):.0f}M, p10={statistics.quantiles(red_rates, n=10)[0]:.0f}M")

        # Expert recommendations (from conversation)
        if wan_name == "Spectrum":
            green_floor = 550
            yellow_floor = 350
            red_floor = 225

            green_floor_ul = 24
            yellow_floor_ul = 14
            red_floor_ul = 7
        else:  # ATT
            green_floor = 45
            yellow_floor = 35
            red_floor = 25

            green_floor_ul = 10
            yellow_floor_ul = 8
            red_floor_ul = 6

        print(f"\n{'='*80}")
        print(f"RECOMMENDED STATE-BASED FLOORS (Expert-Tuned)")
        print(f"{'='*80}")
        print(f"\nDownload:")
        print(f"  GREEN:  {green_floor} Mbps  (enjoy bandwidth when healthy)")
        print(f"  YELLOW: {yellow_floor} Mbps  (early congestion protection)")
        print(f"  RED:    {red_floor} Mbps  (latency survival mode)")
        print(f"\nUpload:")
        print(f"  GREEN:  {green_floor_ul} Mbps")
        print(f"  YELLOW: {yellow_floor_ul} Mbps")
        print(f"  RED:    {red_floor_ul} Mbps")

        print(f"\nCeiling: {current_ceiling} Mbps (unchanged)")
        print()

    def recommend_time_of_day_bias(self):
        """Generate time-of-day floor bias recommendations"""
        print("=" * 80)
        print("TIME-OF-DAY FLOOR BIAS RECOMMENDATIONS")
        print("=" * 80)
        print("\nBias adjusts the base floor dynamically based on historical congestion.")
        print("Positive bias = raise floor during clean periods")
        print("Negative bias = lower floor during congested periods\n")

        print(f"{'Hour':<6} {'Bias':<8} {'Reasoning'}")
        print("-" * 80)

        for hour in sorted(self.hourly_stats.keys()):
            stats = self.hourly_stats[hour]
            total = stats['samples']

            if total < 10:  # Not enough data
                continue

            red_pct = (stats['red'] / total) * 100
            median_delta = statistics.median(stats['deltas'])

            # Expert guidance for bias calculation
            if median_delta < 5 and red_pct < 5:
                bias = "+20%"
                reason = "Very healthy - stretch bandwidth"
            elif median_delta < 8 and red_pct < 15:
                bias = "+10%"
                reason = "Healthy - mild boost"
            elif median_delta < 12 and red_pct < 30:
                bias = "0%"
                reason = "Normal - no adjustment"
            elif median_delta < 20 and red_pct < 50:
                bias = "-15%"
                reason = "Mild congestion - preemptive reduction"
            else:
                bias = "-25%"
                reason = "Heavy congestion - aggressive floor drop"

            print(f"{hour:02d}:00  {bias:<8} {reason}")

        print()

    def show_recent_events(self, minutes: int = 60):
        """Show recent congestion events"""
        if not self.samples:
            return

        latest = self.samples[-1]['timestamp']
        cutoff = latest.timestamp() - (minutes * 60)

        recent = [s for s in self.samples if s['timestamp'].timestamp() >= cutoff]

        if not recent:
            print(f"No samples in last {minutes} minutes\n")
            return

        print("=" * 80)
        print(f"RECENT CONGESTION EVENTS (Last {minutes} minutes)")
        print("=" * 80)
        print(f"{'Time':<20} {'State':<12} {'Delta':<10} {'RTT':<10} {'DL Rate':<10} {'UL Rate'}")
        print("-" * 80)

        for s in recent[-30:]:  # Last 30 samples
            time_str = s['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            state = f"{s['dl_state']}/{s['ul_state']}"
            print(f"{time_str:<20} {state:<12} {s['delta']:>6.1f}ms  {s['rtt']:>6.1f}ms  {s['dl_rate']:>6d}M    {s['ul_rate']:>4d}M")

        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_congestion_patterns.py <log_file> [wan_name] [ceiling_mbps]")
        print("Example: python3 analyze_congestion_patterns.py /var/log/cake_auto.log Spectrum 940")
        sys.exit(1)

    log_file = sys.argv[1]
    wan_name = sys.argv[2] if len(sys.argv) > 2 else "Spectrum"
    ceiling = int(sys.argv[3]) if len(sys.argv) > 3 else 940

    analyzer = CongestionAnalyzer(log_file)
    analyzer.parse_logs()

    if not analyzer.samples:
        print("No data found in log file!")
        sys.exit(1)

    # Run analysis
    analyzer.analyze_hourly_patterns()
    analyzer.recommend_floors(wan_name, ceiling)
    analyzer.recommend_time_of_day_bias()
    analyzer.show_recent_events(minutes=120)

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Review recommended floors above")
    print("2. Update config files with state-based floors")
    print("3. Modify autorate_continuous.py to use dynamic floors")
    print("4. Deploy and monitor for 48-72 hours")
    print("5. Implement time-of-day bias after stable")
    print()


if __name__ == "__main__":
    main()
