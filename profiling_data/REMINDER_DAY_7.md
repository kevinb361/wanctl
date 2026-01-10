# Profiling Day 7 Review - REMINDER

**Target Date:** January 15, 2026 (Wednesday)

## What to Do

1. **Collect Day 7 logs from both containers:**
   ```bash
   # Spectrum
   ssh cake-spectrum 'sudo cp /var/log/wanctl/spectrum_debug.log /tmp/spectrum_debug_day7.log && sudo chmod 644 /tmp/spectrum_debug_day7.log'
   scp cake-spectrum:/tmp/spectrum_debug_day7.log ~/projects/wanctl/profiling_data/spectrum_day7.log

   # ATT
   ssh cake-att 'sudo cp /var/log/wanctl/att_debug.log /tmp/att_debug_day7.log && sudo chmod 644 /tmp/att_debug_day7.log'
   scp cake-att:/tmp/att_debug_day7.log ~/projects/wanctl/profiling_data/att_day7.log
   ```

2. **Run profiling analysis:**
   ```bash
   cd ~/projects/wanctl
   python3 scripts/profiling_collector.py profiling_data/spectrum_day7.log --all
   python3 scripts/profiling_collector.py profiling_data/att_day7.log --all
   ```

3. **Compare with Day 1 baseline:**
   - Check for cycle time drift (should remain ~44ms Spectrum, ~32ms ATT)
   - Monitor P99 values for degradation
   - Count router update frequency
   - Look for weekly patterns (weekday vs weekend)

4. **Document findings:**
   - Create `profiling_data/DAY_7_RESULTS.md` with comparison to Day 1
   - Note any anomalies or patterns
   - Decide if optimization is needed (unlikely based on Day 1)

## Questions to Answer

- [ ] Has cycle time remained stable?
- [ ] Any increase in P99/max latencies?
- [ ] Router update frequency changed?
- [ ] Weekly patterns visible (evening congestion)?
- [ ] Any subsystem showing degradation?
- [ ] Continue to Day 14 or conclude early?

## Expected Outcomes

Based on Day 1 results, we expect:
- Cycle times to remain stable (~44ms Spectrum, ~32ms ATT)
- Continued excellent headroom (>95%)
- Flash wear protection still working (<1% update rate)
- Possible evening congestion patterns emerging

## If Everything Looks Good

Continue collection to Day 14 (January 22) for final statistical confidence.

## If Issues Found

- Investigate any performance degradation
- Check for router/network changes
- Review steering daemon interactions
- Consider Phase 2 optimization if needed (unlikely)

---

**Reminder Set:** 2026-01-10
**Collection Start:** 2026-01-08
**Day 1 Baseline:** profiling_data/DAY_1_RESULTS.md
