#!/usr/bin/env python3
"""Compute Phase 220 Wave 0 golden statistics pins.

Independent stdlib-only reference. The Phase 220 aggregator does not import
this file; Plan 01 uses it to pre-register expected MWU/bootstrap values before
Plan 02 implementation exists.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys

const_x = [1.0] * 60
const_y = [3.0] * 60
rng = random.Random(220)
uniform_x = [float(value) for value in rng.choices([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], k=90)]
uniform_y = [float(value) for value in rng.choices([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], k=90)]

pin_values: dict[str, dict[str, float]] = {}

for label, x_values, y_values in (
    ("mwu_pin_1", const_x, const_y),
    ("mwu_pin_2", uniform_x, uniform_y),
):
    pool = [(value, "x") for value in x_values] + [(value, "y") for value in y_values]
    pool.sort()
    rank_sum_x = 0.0
    tie_sizes: list[int] = []
    index = 0
    while index < len(pool):
        end = index + 1
        while end < len(pool) and pool[end][0] == pool[index][0]:
            end += 1
        mid_rank = (index + 1 + end) / 2.0
        tie_sizes.append(end - index)
        for _, arm in pool[index:end]:
            if arm == "x":
                rank_sum_x += mid_rank
        index = end

    n_x = len(x_values)
    n_y = len(y_values)
    n_total = n_x + n_y
    u_x = rank_sum_x - n_x * (n_x + 1) / 2.0
    mu = n_x * n_y / 2.0
    tie_sum = sum(size**3 - size for size in tie_sizes)
    variance = (n_x * n_y / 12.0) * ((n_total + 1) - tie_sum / (n_total * (n_total - 1)))
    z = (u_x - mu) / math.sqrt(variance)
    phi = 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0)))
    pin_values[label] = {"p": round(2.0 * (1.0 - phi), 8)}

for label, x_values, y_values in (
    ("bootstrap_pin_1", const_x, const_y),
    ("bootstrap_pin_2", uniform_x, uniform_y),
):
    bootstrap_rng = random.Random(220)
    diffs: list[float] = []
    for _ in range(2000):
        sample_x = [bootstrap_rng.choice(x_values) for _ in range(len(x_values))]
        sample_y = [bootstrap_rng.choice(y_values) for _ in range(len(y_values))]
        diffs.append(statistics.median(sample_x) - statistics.median(sample_y))
    diffs.sort()
    pin_values[label] = {
        "ci_lower": round(diffs[int(0.025 * 2000)], 8),
        "ci_upper": round(diffs[int(0.975 * 2000) - 1], 8),
    }

json.dump(pin_values, sys.stdout, indent=2)
sys.stdout.write("\n")
