---
phase: 201-docsis-aware-ul-congestion-control
plan: 12
type: execute
wave: 8
depends_on: [11]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
autonomous: false
requirements: [VALN-06]
tags: [phase-201, wave-8, soak, valn-06-watchdog, closeout, verification]

must_haves:
  truths:
    - "24h Spectrum UL regression soak completed against the v1.42.0 binary that passed Plan 201-11 canary"
    - "UL hysteresis suppression rate over the soak window is < 5/60s mean (D-14 watchdog threshold; no relaxation, no tightening)"
    - "soak-summary.json captures suppression rate, floor-hit count (must be 0), CAKE backlog distribution, and DOCSIS-state transitions"
    - "REVIEWS HIGH-5 (2026-05-04): soak verdict primary gate is `floor_hit_cycles_total` delta across the 24h window (end_value - start_value). Delta == 0 is required for VALN-06 watchdog PASS. The legacy `ul_hysteresis_suppression_rate_per_60s.mean < 5.0` gate is RETAINED as a SECONDARY watchdog signal."
    - "REVIEWS round-5 (2026-05-04): the PRIMARY gate is COLLECTIBLE — Step 1.5 (capture floor_hit_cycles_total at soak T+0, anchored to Plan 201-11 verdict.json `.floor_hit_cycles_total_loaded_window_end` with live `/health` fallback) is REQUIRED before the 24h wait begins. /health exposes only the current counter value; past values cannot be reconstructed at soak end. Skipping Step 1.5 makes the PRIMARY gate uncollectible, which is itself a fail-OPEN — Step 4 detects the missing T+0 baseline and authors `verdict: fail` with reason `soak_primary_gate_uncollectible_t0_baseline_missing`. Daemon restart mid-soak (negative delta) similarly invalidates the gate and produces `soak_primary_gate_uncollectible_negative_delta_<N>`."
    - "201-VERIFICATION.md records the closure verdict (passed/failed/blocked) with per-criterion evidence pointers"
    - "REQUIREMENTS.md flips VALN-06 to satisfied (or records the failure) with traceability to 201-VERIFICATION.md"
    - "STATE.md updated with phase closure (reflecting milestone v1.42 status)"
    - "201-VALIDATION.md `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
      provides: "Standardized soak metrics: suppression rate, floor hits, distribution stats"
      contains: "suppressions_per_60s_mean"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
      provides: "Phase 201 closure verdict + per-criterion evidence pointers"
      contains: "VALN-06"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
      provides: "Operator-readable soak outcome + closeout decisions"
      contains: "Soak verdict"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md"
      to: ".planning/REQUIREMENTS.md VALN-06 row"
      via: "VALN-06 satisfied / failed status references this VERIFICATION.md"
      pattern: "VALN-06"
---

<objective>
Wave 7 24h soak watchdog + phase closeout. The soak is the regression watchdog (NOT the verdict — Plan 201-11 canary is the verdict per VALN-06 closure shape). The soak validates that the new control mode behaves stably over 24h without spurious oscillation, with UL hysteresis suppression rate < 5/60s mean (D-14 unchanged from Phase 200 closure shape).

Per RESEARCH and CONTEXT: tightening to <2/60s is deferred to v1.43+; relaxing is forbidden. Same fail-closed shape: if soak fails, that's a regression signal — escalate to gap-closure planning.

After the soak passes, this plan finalizes phase closure: writes 201-VERIFICATION.md, flips REQUIREMENTS.md VALN-06 to satisfied, updates STATE.md, marks VALIDATION.md as nyquist-compliant.

Output: Soak capture + verdict; 201-VERIFICATION.md (canonical phase closure); REQUIREMENTS.md + STATE.md updated; VALIDATION.md frontmatter flipped to compliant.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Run 24h Spectrum UL regression soak; capture suppression-rate distribution</name>
  <what-built>
    Plan 201-11 canary passed: zero floor hits at setpoint=12. v1.42.0 is live in production. 24h watchdog window now begins.
  </what-built>
  <how-to-verify>
    Operator MUST execute:

    1. **(Round-9 — atomic capture, no longer separate from Step 1.5):** Step 1's prior responsibility (recording `soak_start_utc`) has moved into Step 1.5. The two captures (`soak_start_utc` and `floor_hit_cycles_total_start`) are now a single atomic write so they always represent the same soak run. **Do not write the env file separately at this step** — proceed directly to Step 1.5. (This change closes the round-9 staleness class: previously `>>`-append across soak attempts could accumulate stale `soak_start_utc=` and `floor_hit_cycles_total_start=` lines from prior failed attempts; the file would pass the round-8 line-shape validator but represent multiple incoherent captures layered together.)

    1.5. **ATOMIC CAPTURE OF SOAK-START STATE** (REVIEWS HIGH-5 + round-5/9: this MUST happen at soak T+0 — `/health.upload.floor_hit_cycles_total` is a live in-process counter; past values cannot be reconstructed at soak end. Skipping this step makes the PRIMARY soak gate uncollectible. Round-9: also unifies `soak_start_utc` capture into the same write so the timestamp and counter baseline are guaranteed to be a temporally-coherent pair.):

       **Required invariants for `/tmp/phase201-soak.env`:** the file MUST contain ONLY `key=value` assignments after this step (no warnings, no commentary, no narration), so that Step 4's `source /tmp/phase201-soak.env` is a clean, deterministic load. All informational output goes to stderr. All values are validated as digit-only integers before being written. The provenance label is set from the code path that actually produced the value, NOT from a leftover variable.

       ```bash
       set -euo pipefail

       PHASE_DIR=.planning/phases/201-docsis-aware-ul-congestion-control
       ENV_FILE=/tmp/phase201-soak.env

       # Strict env-file validator (round-8: KEY-WHITELIST, not just value-charset).
       #
       # Rationale: this file gets sourced by Step 4. The round-7 validator
       # rejected dangerous characters in VALUES but allowed arbitrary KEY names —
       # which means lines like `PATH=/tmp/evil:/bin`, `IFS=,`, `BASH_ENV=/tmp/evil.sh`,
       # `PROMPT_COMMAND='rm -rf /'`, `LD_PRELOAD=/tmp/evil.so`, or
       # `BASH_FUNC_foo%%=evil` would all match the value-shape regex and on
       # `source` would poison the shell state. Every one of those has a clean
       # value-charset; what makes them dangerous is the KEY identity.
       #
       # This validator whitelists THE EXACT THREE KEYS Step 1 + Step 1.5 are
       # allowed to write, each with its own per-key value charset. Anything
       # else — unknown keys, magic env vars (PATH/IFS/etc.), function-export
       # attacks, malformed entries — is rejected.
       #
       # Allowed entries:
       #   soak_start_utc=ISO-8601-Z           (Step 1; charset: [0-9T:Z-]+)
       #   floor_hit_cycles_total_start=NNN    (Step 1.5; charset: [0-9]+)
       #   floor_hit_cycles_total_start_source="…"   (Step 1.5; quoted; charset:
       #                                              [A-Za-z0-9._/:-]+)
       # Validator (round-8 whitelist + round-9 cardinality):
       #   - Each non-empty, non-comment line must be one of the 3 allowed
       #     KEY=VALUE shapes (round-8 closed-set whitelist).
       #   - Each key must appear EXACTLY ONCE (round-9 cardinality). Previously
       #     the validator accepted multiple `soak_start_utc=` or
       #     `floor_hit_cycles_total_start=` lines as long as each individually
       #     matched the whitelist regex — but that allows stale data from a
       #     prior failed soak to persist and silently mix with fresh data.
       #     `source` would last-write-win, which is correct for the variable
       #     value but disguises the fact that the file represents multiple
       #     incoherent capture sessions. Cardinality == 1 forces atomic-fresh.
       #   - All 3 keys must be present after the write (round-9 completeness).
       validate_env_file() {
           local file="$1"
           local mode="${2:-strict}"   # "strict" requires all 3 keys with cardinality 1;
                                        # "lenient" allows empty/missing/incomplete (used to inspect
                                        # pre-existing files before atomic replacement)
           local violations
           violations=$(awk '
               BEGIN { soak_start_utc=0; floor_start=0; floor_src=0 }
               /^[[:space:]]*$/                                                              { next }
               /^[[:space:]]*#/                                                              { next }
               /^soak_start_utc=[0-9TZ:-]+$/                                                 { soak_start_utc++; next }
               /^floor_hit_cycles_total_start=[0-9]+$/                                       { floor_start++; next }
               /^floor_hit_cycles_total_start_source="[A-Za-z0-9._\/:-]+"$/                  { floor_src++; next }
               { print "line " NR ": shape violation: " $0 }
               END {
                   if (soak_start_utc > 1) print "cardinality violation: soak_start_utc appears " soak_start_utc " times (must be exactly 1)"
                   if (floor_start    > 1) print "cardinality violation: floor_hit_cycles_total_start appears " floor_start " times (must be exactly 1)"
                   if (floor_src      > 1) print "cardinality violation: floor_hit_cycles_total_start_source appears " floor_src " times (must be exactly 1)"
               }
           ' "$file")
           if [[ -n "$violations" ]]; then
               echo "ABORT: $file failed validation (round-8 whitelist + round-9 cardinality):" >&2
               echo "$violations" >&2
               echo "ABORT: Allowed keys (each appears exactly once after Step 1.5): soak_start_utc, floor_hit_cycles_total_start, floor_hit_cycles_total_start_source." >&2
               return 1
           fi
           # In strict mode, also verify all 3 keys are present (completeness).
           if [[ "$mode" == "strict" ]]; then
               local missing
               missing=$(awk '
                   BEGIN { soak_start_utc=0; floor_start=0; floor_src=0 }
                   /^soak_start_utc=/                                                            { soak_start_utc++ }
                   /^floor_hit_cycles_total_start=/                                              { floor_start++ }
                   /^floor_hit_cycles_total_start_source=/                                       { floor_src++ }
                   END {
                       if (soak_start_utc == 0) print "missing key: soak_start_utc"
                       if (floor_start    == 0) print "missing key: floor_hit_cycles_total_start"
                       if (floor_src      == 0) print "missing key: floor_hit_cycles_total_start_source"
                   }
               ' "$file")
               if [[ -n "$missing" ]]; then
                   echo "ABORT: $file is missing required keys (round-9 completeness):" >&2
                   echo "$missing" >&2
                   return 1
               fi
           fi
           return 0
       }

       # ROUND-11 ABORT-PATH DEFENSE: back up any pre-existing $ENV_FILE
       # IMMEDIATELY, before any operation that could fail. This ensures the
       # invariant: at any moment after Step 1.5 begins, $ENV_FILE either
       # contains a valid fresh capture from THIS run, or does not exist at
       # all. No third state — including "stale file from a prior run" — is
       # reachable.
       #
       # Round-10's trap-cleanup of $TMP_ENV_FILE handles the case where
       # Step 1.5 fails AFTER mktemp (the temp file is removed). But it left
       # the prior $ENV_FILE intact, so an operator who runs Step 1.5, hits
       # an abort (e.g., neither anchor available, jq fails, ssh times out),
       # and then absent-mindedly proceeds to Step 4 would have Step 4 source
       # the STALE prior file. The validator cannot catch this if the prior
       # file was itself produced by a once-successful Step 1.5 (it's
       # well-formed, just from a different soak run).
       #
       # Pattern: rename the prior file to .stale.<TS> as the FIRST step.
       # Forensics is preserved (operator can inspect the .stale.* file for
       # context after an abort) but $ENV_FILE no longer exists, so Step 4's
       # missing-file branch fires correctly and authors verdict: fail with
       # reason soak_primary_gate_uncollectible_t0_baseline_missing.
       #
       # rename(2) within the same filesystem is atomic, so concurrent readers
       # never see a partial state. The .stale.<TS> name is dot-prefixed so
       # ls listings don't clutter the operator's view.
       if [[ -f "$ENV_FILE" ]]; then
           STALE_BACKUP="${ENV_FILE}.stale.$(date -u +%Y%m%dT%H%M%SZ)"
           # If the timestamp collides (Step 1.5 re-run within the same second),
           # mktemp-style suffix avoids overwriting an existing backup.
           if [[ -e "$STALE_BACKUP" ]]; then
               STALE_BACKUP=$(mktemp -p "$(dirname "$ENV_FILE")" \
                   ".$(basename "$ENV_FILE").stale.XXXXXX")
               # mktemp creates an empty file; remove it so mv-f doesn't
               # truncate-and-replace what's there.
               rm -f -- "$STALE_BACKUP"
           fi
           mv -f -- "$ENV_FILE" "$STALE_BACKUP"

           # Lenient validation of the moved-aside file — informational only,
           # surfaces whether the prior file was conformant. Does not affect
           # Step 1.5's flow (we're going to write a fresh file regardless).
           validate_env_file "$STALE_BACKUP" lenient || {
               echo "INFO: pre-existing $ENV_FILE was non-conformant; backed up to $STALE_BACKUP for forensics." >&2
           }
           echo "INFO: backed up pre-existing $ENV_FILE to $STALE_BACKUP (round-11: aborted Step 1.5 must not leave stale data sourceable)." >&2
       fi
       # POSTCONDITION OF THIS BLOCK: $ENV_FILE does not exist. Step 4 will
       # correctly detect a missing file if Step 1.5 aborts before the rename.

       # Round-10 TRUE-ATOMIC capture via mktemp + write + validate + rename.
       # Pattern: write to a temp file (same directory ⇒ same filesystem),
       # validate the temp file in strict mode, then rename into place. The
       # trap cleans up the temp file on any exit (success, failure, signal)
       # so we never leave half-written files behind.
       TMP_ENV_FILE=$(mktemp -p "$(dirname "$ENV_FILE")" ".$(basename "$ENV_FILE").tmp.XXXXXX")
       trap 'rm -f -- "$TMP_ENV_FILE"' EXIT

       # Find the most recent canary verdict.json. `|| true` prevents set-e abort
       # on no-match; `2>/dev/null` suppresses ls's "no such file" stderr noise.
       CANARY_VERDICT=$(ls -1t "$PHASE_DIR"/canary/*/verdict.json 2>/dev/null | head -1 || true)

       FLOOR_HIT_T0=""
       SOURCE=""

       # Try anchor 1: Plan 201-11 verdict.json `.floor_hit_cycles_total_loaded_window_end`.
       # This is the canonical anchor — by construction, the canary's last counter
       # value is identical to soak T+0 (no cycles between canary loaded-window end
       # and soak start, modulo bounded deploy/restart time).
       if [[ -n "$CANARY_VERDICT" && -s "$CANARY_VERDICT" ]]; then
           candidate=$(jq -r '.floor_hit_cycles_total_loaded_window_end // empty' "$CANARY_VERDICT" 2>/dev/null || true)
           if [[ "$candidate" =~ ^[0-9]+$ ]]; then
               FLOOR_HIT_T0="$candidate"
               SOURCE="verdict.json:$CANARY_VERDICT"
           fi
       fi

       # Try anchor 2 (fallback): live /health sample. Only used when verdict.json
       # is missing OR predates Plan 08-T3 (field absent). Operator should be aware
       # this introduces deploy-latency drift between canary end and soak start.
       if [[ -z "$FLOOR_HIT_T0" ]]; then
           candidate=$(ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" 2>/dev/null \
               | jq -r '.wans[0].upload.floor_hit_cycles_total // empty' 2>/dev/null || true)
           if [[ "$candidate" =~ ^[0-9]+$ ]]; then
               FLOOR_HIT_T0="$candidate"
               SOURCE="live_health"
           fi
       fi

       # Hard-fail if neither anchor produced a valid integer. PRIMARY soak gate
       # is uncollectible; better to FAIL the procedure NOW than 24 hours from now.
       if [[ -z "$FLOOR_HIT_T0" ]]; then
           echo "ABORT: floor_hit_cycles_total_start unavailable from both verdict.json (${CANARY_VERDICT:-not found}) and live /health." >&2
           echo "ABORT: PRIMARY soak gate is uncollectible. Restore /health.upload.floor_hit_cycles_total (Plan 05) and/or fix verdict.json (Plan 08-T3), then re-run Step 1.5." >&2
           exit 2
       fi

       # Validate the SOURCE label against the same shape rules before we write
       # it. The fallback path's "live_health" is plain alphanumeric — passes the
       # bare-value rule. The verdict.json path's "verdict.json:.planning/.../verdict.json"
       # contains slash and colon — passes the bare-value rule
       # ([A-Za-z0-9._/:-]). If a future code path produces a SOURCE that
       # contains spaces, dollar signs, or backticks, this regex rejects it
       # before write — preventing the lying-provenance class of round 6 from
       # becoming the injection class of round 7.
       if [[ ! "$SOURCE" =~ ^[A-Za-z0-9._/:-]+$ ]]; then
           echo "ABORT: SOURCE label '$SOURCE' contains characters that would break sourceability. Either fix the producer to emit only [A-Za-z0-9._/:-] characters, or extend the validator AND the consumer to handle the new shape consistently." >&2
           exit 2
       fi

       # Compute soak_start_utc HERE (atomic with counter capture) so the
       # timestamp and counter baseline are guaranteed to represent the same
       # moment-in-time. Round-9 fix preserved: soak_start_utc and
       # floor_hit_cycles_total_start are captured in the same script block.
       SOAK_START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

       # Write the entire content to the TEMP file in one block. Concurrent
       # readers of $ENV_FILE see the old file (or no file); they cannot
       # observe the temp file's intermediate states because the temp name
       # is dot-prefixed and randomized.
       {
           echo "soak_start_utc=$SOAK_START_UTC"
           echo "floor_hit_cycles_total_start=$FLOOR_HIT_T0"
           echo "floor_hit_cycles_total_start_source=\"$SOURCE\""
       } > "$TMP_ENV_FILE"

       # Validate the temp file BEFORE making it visible at $ENV_FILE.
       # If validation fails, the trap removes the temp file and the
       # existing (possibly-prior-good) $ENV_FILE is untouched. No
       # half-published states.
       validate_env_file "$TMP_ENV_FILE" strict || {
           echo "ABORT: pre-rename validation of $TMP_ENV_FILE failed — Step 1.5's write was non-conformant, incomplete, or had wrong cardinality. The existing $ENV_FILE (if any) is unchanged. Inspect Step 1.5's logic before continuing." >&2
           exit 2
       }

       # Atomic rename — POSIX rename(2) within the same filesystem is
       # atomic. Any concurrent reader of $ENV_FILE sees either the old
       # file or the new file, never a partial. The trap (set above)
       # would clean up $TMP_ENV_FILE if mv failed; on success the temp
       # file no longer exists at the temp path, and the trap is a no-op.
       mv -f -- "$TMP_ENV_FILE" "$ENV_FILE" || {
           echo "ABORT: atomic rename $TMP_ENV_FILE -> $ENV_FILE failed (likely cross-filesystem or permissions). The existing $ENV_FILE (if any) is unchanged." >&2
           exit 2
       }
       # Rename succeeded; clear the trap target so EXIT trap is no-op.
       trap - EXIT

       # Post-rename verification: re-read $ENV_FILE and validate. Catches
       # the unlikely case where mv-f succeeded but a concurrent writer
       # raced our rename. Round-9 strict mode (cardinality + completeness
       # + whitelist).
       validate_env_file "$ENV_FILE" strict || {
           echo "ABORT: post-rename verification of $ENV_FILE failed — file was modified by a concurrent writer between rename and verification. The PRIMARY soak gate evidence is unreliable; do not begin the soak. Investigate the concurrent writer." >&2
           exit 2
       }

       # Operator-visible confirmation (stderr, not $ENV_FILE):
       echo "Step 1.5 complete: floor_hit_cycles_total_start=$FLOOR_HIT_T0 (source: $SOURCE) recorded in $ENV_FILE" >&2
       ```

       **Why this is structured this way (lessons from rounds 1-13):**
       - `set -euo pipefail` so any unbound var or pipeline failure aborts; no silent partial writes.
       - `|| true` only on `ls` no-match (legitimate empty case), not on `jq`/`ssh` failures (those should propagate).
       - The `SOURCE` variable is set inside each successful branch, never inferred post-hoc from leftover state (round-6 catch).
       - Strict integer regex validation (`^[0-9]+$`) on the counter value — empty string, `null`, `"-1"`, `"1.0"` all rejected.
       - The env file gets ONLY `key=value` lines. Commentary, warnings, success messages all go to **stderr** (round-6 catch).
       - **Validation uses an `awk` whitelist filter, NOT `bash -n` (round-7) and NOT a value-charset blacklist (round-8).** Whitelisting constrains keys to the EXACT THREE Step 1.5 writes, each with its per-key value charset, blocking magic env vars (`PATH=`, `IFS=`, `BASH_ENV=`, `LD_PRELOAD=`, `PROMPT_COMMAND=`, `BASH_FUNC_xxx%%=`) that poison shell state without using a single metacharacter.
       - **Cardinality + completeness validation (round-9 catch).** Each whitelisted key appears EXACTLY ONCE; in strict mode all 3 must be present. Previously `>>`-appended files where prior failed soak attempts left stale duplicates passed line-shape but represented multiple incoherent capture sessions; cardinality enforcement closes that.
       - **TRUE atomic file replacement (round-10 catch).** Step 1.5 writes to a temp file in the same directory, validates the temp file in strict mode, then `mv -f` (POSIX `rename(2)`, atomic within the same filesystem) into place. Round-9's `: > FILE` + `{ ... } > FILE` was NOT atomic — sequential writes have visibility windows. Rename(2) gives true POSIX atomicity.
       - **Abort-path stale-file defense (round-11 catch).** Round-10's trap cleans up the temp file on any failure path, but left the *prior* `$ENV_FILE` intact. Round-11 fix: at the START of Step 1.5, atomically rename any pre-existing `$ENV_FILE` to `.stale.<TS>`. Postcondition: at every moment after this block, `$ENV_FILE` either contains a valid fresh capture from THIS run, or does not exist at all.
       - **Consumer actually exits on failure (round-12 catch).** Explicit `SOAK_VERDICT` / `SOAK_FAIL_REASON` script variables; `write_soak_summary_and_exit` helper; every failure branch calls it; consumer never falls through past a detected failure. Plus: validator early-fails on missing/unreadable file. Plus: T+24h capture validates `FLOOR_HIT_T24` is a non-negative integer before arithmetic. Plus: post-source variable-set assertions catch TOCTOU races.
       - **Helper survives shell-state-leakage between procedure steps (round-13 catch).** Step 4 may run in a separate bash invocation from Step 1.5 (operator opens a new tmux pane 24h later, or `systemd-run` executes Step 4 as a scheduled job). Variables defined inside Step 1.5's bash block are NOT visible at Step 4. Round-12's `write_soak_summary_and_exit` helper had `local out_dir="${OUT:-$PHASE_DIR/soak/...}"` — under `set -u`, unbound `$PHASE_DIR` aborted the function at the variable expansion *before* mkdir/jq/exit could run. Round-13 fix: (a) Step 4 has its own preamble that re-establishes `PHASE_DIR` and `ENV_FILE` from hardcoded literals; (b) the helper disables `set -eu` internally so no preceding failure prevents the exit; (c) hardcoded fallback for `PHASE_DIR` inside the helper if even the preamble didn't run; (d) timestamp prefers `soak_start_utc` (real soak start) over `date -u +now` (which would produce a directory name detached from the actual soak); (e) jq fallback to printf-built JSON if jq is missing; (f) operator-visible verdict mirror to stderr so a failed disk write doesn't hide the verdict. The helper's contract — "always write summary, always exit with the right code" — now actually holds across all reachable shell states.
       - **Trap-cleanup of the temp file** (`trap 'rm -f "$TMP_ENV_FILE"' EXIT`). Any exit path — success, validation failure, signal, OOM kill — removes the temp file. On successful rename, the temp path no longer exists, so the trap is a no-op. No leaked half-written files.
       - **Three-checkpoint validation (rounds 7+8+9+10).** Pre-existing-file lenient validation (informational; surfaces legacy contamination), pre-rename strict validation on the temp file (refuses to publish an invalid file), post-rename strict re-validation on the live file (catches the rare case of a concurrent writer racing our rename). All three checkpoints use the same closed-set whitelist + cardinality validator.
       - **The `SOURCE` label is itself validated against the bare-value charset before writing** (round-7 catch reinforced).

       **Failure modes Step 1.5 closes:**
       - **Step 1.5 never run** → `$ENV_FILE` doesn't exist; Step 4's missing-file branch fires; verdict: fail with reason `soak_primary_gate_uncollectible_t0_baseline_missing`.
       - **Step 1.5 ran but aborted before rename** (anchor unavailable, jq failure, ssh timeout, `mktemp` failure) → round-11 has already moved the prior file to `.stale.<TS>`; round-10 trap removed the temp file; `$ENV_FILE` does not exist; Step 4's missing-file branch fires. The `.stale.<TS>` file is available for forensics but is NOT sourced.
       - **Step 1.5 ran and succeeded** → atomic rename produces a valid fresh `$ENV_FILE`; Step 4 sources cleanly.
       - **Step 1.5 ran with verdict.json predating Plan 08-T3** → fallback to `live_health`; provenance label honestly records the source so post-mortem can compare.
       - **Operator manually copies a `.stale.<TS>` file back to `$ENV_FILE`** → strict validator accepts the (well-formed) content but the operator-discipline contract was violated. The decision matrix's coherence check (round-9: cardinality, completeness) cannot detect a temporally-stale-but-otherwise-valid file. This is the residual operator-discipline gap; mitigation is to encode the rule "do not promote `.stale.*` files" in operator runbook + soak-summary.json's `floor_hit_cycles_total_start_source` field provenance audit trail.

    2. **Schedule soak finish capture** (24h + 30 min for summarization):
       ```
       systemd-run --user --on-active=24h30m --unit=phase201-soak-finish \
           bash -c 'bash scripts/phase201-soak-finish.sh > /tmp/phase201-soak-finish.log 2>&1'
       ```
       (If `scripts/phase201-soak-finish.sh` does not exist, the soak finish is run manually at the 24h mark; the script is optional automation.)

    3. **Live monitoring (optional, NOT a gate)** — operator can periodically check:
       ```
       ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" \
           | jq '.wans[0].upload | {state, hysteresis: .hysteresis | {suppressions_per_min, transitions_suppressed, alert_threshold_per_min}, headroom_state, rtt_integral_ms_s, cake_aligned}'
       ```

    4. **At soak end (~24h after start)**, capture the soak summary. The summary MUST include:
       - `soak_start_utc`, `soak_end_utc`, `soak_duration_s` (>= 86_400)
       - `floor_hit_cycles_total_start`, `floor_hit_cycles_total_end`, `floor_hit_cycles_total_delta` (PRIMARY gate — must be 0; cycle-fidelity 50ms counter, REVIEWS HIGH-5)
       - `floor_hits_during_soak_1hz_secondary` (1 Hz snapshot count — must also be 0; cross-check)
       - `ul_hysteresis_suppression_rate_per_60s_p50`, `_p95`, `_mean` (D-14 SECONDARY gate — `_mean` must be < 5.0)
       - `headroom_state_distribution` (counts of AVAILABLE/EXHAUSTED across the soak)
       - `cake_aligned_distribution` (counts of true/false across the soak)
       - `rtt_integral_ms_s` quartiles + max
       - Daemon restart count during soak (INFRASTRUCTURE gate — must be 0)
       - Any non-INFO log lines (errors/warnings) flagged

       Example synthesis (REQUIRED steps, not optional — operator can adapt to local tooling but the PRIMARY-gate capture commands are not skippable):
       ```bash
       set -euo pipefail

       # ROUND-13 STEP-4 PREAMBLE: re-establish all variables this step needs.
       # Step 4 may run in a separate bash invocation from Step 1.5 (e.g., the
       # operator opens a new tmux pane 24h later, or systemd-run executes the
       # Step 4 block as a scheduled job). Variables defined inside Step 1.5's
       # bash block are NOT visible here — only files on disk persist across
       # bash invocations. Hardcode all literals.
       PHASE_DIR=.planning/phases/201-docsis-aware-ul-congestion-control
       ENV_FILE=/tmp/phase201-soak.env

       # ROUND-8/9 DEFENSE: Re-validate the env file BEFORE source IN STRICT MODE
       # (cardinality + completeness + shape), because a 24h window separates
       # Step 1.5's write from Step 4's source. During that window the file
       # could have been touched by the operator, another process, or a
       # malicious actor with /tmp write access — adding stale lines, deleting
       # required keys, or appending magic env vars. Strict mode catches:
       #   - whitelist violations (round-8: PATH=/etc/evil, BASH_ENV=...)
       #   - duplicate keys (round-9: stale + fresh layered together)
       #   - missing keys (round-9: incomplete capture)
       # Re-paste the validate_env_file function from Step 1.5 (or operator
       # sources a shared helper if one exists in the canary toolkit).
       validate_env_file() {
           local file="$1"
           local mode="${2:-strict}"
           # Round-12 defense: early-fail on missing/unreadable file.
           # Without this, awk would error noisily but the function might
           # falsely return 0 because the violations capture would be empty.
           if [[ ! -f "$file" ]]; then
               echo "ABORT: validator called on missing file: $file" >&2
               return 1
           fi
           if [[ ! -r "$file" ]]; then
               echo "ABORT: validator called on unreadable file: $file" >&2
               return 1
           fi
           local violations
           violations=$(awk '
               BEGIN { soak_start_utc=0; floor_start=0; floor_src=0 }
               /^[[:space:]]*$/                                                              { next }
               /^[[:space:]]*#/                                                              { next }
               /^soak_start_utc=[0-9TZ:-]+$/                                                 { soak_start_utc++; next }
               /^floor_hit_cycles_total_start=[0-9]+$/                                       { floor_start++; next }
               /^floor_hit_cycles_total_start_source="[A-Za-z0-9._\/:-]+"$/                  { floor_src++; next }
               { print "line " NR ": shape violation: " $0 }
               END {
                   if (soak_start_utc > 1) print "cardinality violation: soak_start_utc appears " soak_start_utc " times (must be exactly 1)"
                   if (floor_start    > 1) print "cardinality violation: floor_hit_cycles_total_start appears " floor_start " times (must be exactly 1)"
                   if (floor_src      > 1) print "cardinality violation: floor_hit_cycles_total_start_source appears " floor_src " times (must be exactly 1)"
               }
           ' "$file")
           if [[ -n "$violations" ]]; then
               echo "ABORT: $file failed pre-source validation:" >&2
               echo "$violations" >&2
               return 1
           fi
           if [[ "$mode" == "strict" ]]; then
               local missing
               missing=$(awk '
                   BEGIN { soak_start_utc=0; floor_start=0; floor_src=0 }
                   /^soak_start_utc=/                  { soak_start_utc++ }
                   /^floor_hit_cycles_total_start=/    { floor_start++ }
                   /^floor_hit_cycles_total_start_source=/ { floor_src++ }
                   END {
                       if (soak_start_utc == 0) print "missing key: soak_start_utc"
                       if (floor_start    == 0) print "missing key: floor_hit_cycles_total_start"
                       if (floor_src      == 0) print "missing key: floor_hit_cycles_total_start_source"
                   }
               ' "$file")
               if [[ -n "$missing" ]]; then
                   echo "ABORT: $file is missing required keys:" >&2
                   echo "$missing" >&2
                   return 1
               fi
           fi
           return 0
       }

       # ROUND-12 EXPLICIT VERDICT TRACKING: round-11's plan prose said "if
       # Step 1.5 aborts, $ENV_FILE doesn't exist, Step 4's missing-file
       # branch fires correctly, soak is authored as FAIL." But the previous
       # implementation just printed FAIL: to stderr and FELL THROUGH — no
       # exit, no return, no early branch. Subsequent code called
       # validate_env_file on a missing file (undefined behavior), then
       # source on a missing file (silently leaves vars unset), then
       # arithmetic on an unset variable (set -u trap, or worse, with
       # undefined fallback).
       #
       # Fix: track verdict + reason in explicit script variables, set them
       # on every failure branch, take a SINGLE EXIT path that writes
       # soak-summary.json from those variables. Code structure must make
       # the FAIL path actually execute the summary-write logic, not rely
       # on aspirational comments next to fall-through echo statements.
       SOAK_VERDICT="pending"
       SOAK_FAIL_REASON=""

       write_soak_summary_and_exit() {
           # Round-13 hardening: this helper is called from EARLY-FAIL paths
           # (missing file, contaminated env, T+24h capture failure) AS WELL
           # AS the success path. Early-fail paths run BEFORE OUT, soak_start_utc,
           # FLOOR_HIT_T24, etc. are set. Previous implementation aborted at
           # `local out_dir="${OUT:-$PHASE_DIR/soak/...}"` because $PHASE_DIR
           # might be unbound under set -u (set in Step 1.5's bash block, not
           # this one) — and even if PHASE_DIR is set, mkdir/jq failures
           # under set -e would abort BEFORE the explicit exit calls run.
           #
           # The contract: this helper ALWAYS writes a summary (best-effort)
           # AND ALWAYS exits with the right code. Both promises must hold
           # even when called early, even on filesystems with disk-full /
           # permissions errors, even when /jq/ /mkdir/ are missing.
           #
           # Disable set -e/-u INSIDE the function so no preceding step's
           # failure prevents the exit from running.
           set +eu

           # Resolve out_dir from progressively-weaker sources. PHASE_DIR
           # has a hardcoded default literal in case Step 4's preamble
           # didn't run. Timestamp prefers soak_start_utc (the actual soak
           # start), falls back to "now".
           local pd="${PHASE_DIR:-.planning/phases/201-docsis-aware-ul-congestion-control}"
           local ts=""
           if [[ -n "${soak_start_utc:-}" ]]; then
               ts=$(date -u -d "$soak_start_utc" +%Y%m%dT%H%M%SZ 2>/dev/null)
           fi
           if [[ -z "$ts" ]]; then
               ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null)
           fi
           if [[ -z "$ts" ]]; then
               ts="unknown_$$"
           fi
           local out_dir="${OUT:-$pd/soak/$ts}"

           # Best-effort directory creation. If mkdir fails, we still exit
           # with the right code; the operator sees the verdict in stderr
           # below.
           mkdir -p "$out_dir" 2>/dev/null

           # Best-effort jq write. If jq is missing or fails, fall back to
           # a hand-built JSON via printf so we still leave forensics on disk.
           if command -v jq >/dev/null 2>&1; then
               jq -n \
                   --arg verdict "$SOAK_VERDICT" \
                   --arg reason  "$SOAK_FAIL_REASON" \
                   --arg start_utc "${soak_start_utc:-unknown}" \
                   --arg counter_start "${floor_hit_cycles_total_start:-unknown}" \
                   --arg counter_source "${floor_hit_cycles_total_start_source:-unknown}" \
                   '{verdict: $verdict, reason: $reason, partial_evidence: true,
                     soak_start_utc: $start_utc,
                     floor_hit_cycles_total_start: $counter_start,
                     floor_hit_cycles_total_start_source: $counter_source}' \
                   > "$out_dir/soak-summary.json" 2>/dev/null
           else
               # jq absent — emit minimal valid JSON via printf as fallback.
               printf '{"verdict":"%s","reason":"%s","partial_evidence":true,"soak_start_utc":"%s","floor_hit_cycles_total_start":"%s","floor_hit_cycles_total_start_source":"%s","jq_unavailable":true}\n' \
                   "$SOAK_VERDICT" \
                   "$SOAK_FAIL_REASON" \
                   "${soak_start_utc:-unknown}" \
                   "${floor_hit_cycles_total_start:-unknown}" \
                   "${floor_hit_cycles_total_start_source:-unknown}" \
                   > "$out_dir/soak-summary.json" 2>/dev/null
           fi

           # ALWAYS mirror the verdict to stderr so the operator sees it
           # even if the summary write failed (disk full, permissions, etc.).
           # This is the operator-visible signal that the helper actually ran.
           echo "==========================================" >&2
           echo "SOAK VERDICT: $SOAK_VERDICT" >&2
           echo "Reason:       ${SOAK_FAIL_REASON:-(none)}" >&2
           echo "Summary path: $out_dir/soak-summary.json" >&2
           echo "==========================================" >&2

           # ALWAYS exit with the right code. These exits MUST run even if
           # everything above failed.
           if [[ "$SOAK_VERDICT" == "pass" ]]; then
               exit 0
           elif [[ "$SOAK_VERDICT" == "abort" ]]; then
               exit 2
           else
               exit 1
           fi
       }

       # Pre-source check 1: file must exist. Round-11's backup-on-entry at
       # Step 1.5 ensures aborted Step 1.5 leaves no $ENV_FILE; Step 4 must
       # actually USE that signal, not just acknowledge it.
       if [[ ! -f "$ENV_FILE" ]]; then
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_uncollectible_t0_baseline_missing"
           echo "FAIL: $ENV_FILE missing — Step 1.5 was not executed at soak start, OR aborted before atomic rename. Round-11 invariant: missing $ENV_FILE means PRIMARY soak gate baseline was never captured. Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi

       # Pre-source check 2: strict-mode validation (round-8 whitelist +
       # round-9 cardinality + completeness). validate_env_file itself must
       # also early-fail on missing file (defense in depth).
       if ! validate_env_file "$ENV_FILE" strict; then
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_env_file_contaminated"
           echo "FAIL: $ENV_FILE was contaminated, incomplete, or had duplicate keys between Step 1.5 (write) and Step 4 (read). PRIMARY soak gate evidence is unreliable. Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi

       # Validation passed; safe to source. (Variables loaded into the shell.)
       source "$ENV_FILE"

       # Pre-source check 3: post-source sanity — round-9's strict mode
       # validates cardinality and completeness BEFORE source; this check
       # is defense-in-depth in case `source` itself fails (e.g., file
       # disappears between validation and source — TOCTOU window).
       if [[ -z "${floor_hit_cycles_total_start:-}" ]] \
           || [[ -z "${soak_start_utc:-}" ]] \
           || [[ -z "${floor_hit_cycles_total_start_source:-}" ]]; then
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_post_source_variables_unset"
           echo "FAIL: required variables not set after sourcing $ENV_FILE — possible TOCTOU race between validation and source. Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi

       # Defense-in-depth: re-assert the captured value is a non-negative
       # integer (the validator already enforced this via regex, but a TOCTOU
       # race could deliver a different file).
       if ! [[ "$floor_hit_cycles_total_start" =~ ^[0-9]+$ ]]; then
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_post_source_value_invalid"
           echo "FAIL: floor_hit_cycles_total_start='$floor_hit_cycles_total_start' is not a non-negative integer after sourcing $ENV_FILE. Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi

       if [[ -z "${floor_hit_cycles_total_start:-}" ]]; then
           echo "FAIL: PRIMARY soak gate uncollectible — Step 1.5 was not executed at soak start (or env file failed validation). Authoring verdict: fail." >&2
           # Continue to write soak-summary.json with verdict: fail and the
           # uncollectible reason, then exit non-zero.
       fi

       # Capture T+24h counter live, validate, compute delta. Round-12: explicit
       # verdict-set on every failure path (no fall-through with aspirational
       # "FAIL: ..." echoes).
       FLOOR_HIT_T24=$(ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" 2>/dev/null \
           | jq -r '.wans[0].upload.floor_hit_cycles_total // empty' 2>/dev/null || true)
       if ! [[ "$FLOOR_HIT_T24" =~ ^[0-9]+$ ]]; then
           SOAK_VERDICT="abort"
           SOAK_FAIL_REASON="soak_t24_capture_unavailable"
           echo "ABORT: T+24h /health.upload.floor_hit_cycles_total unavailable or non-integer ('$FLOOR_HIT_T24'). Network issue, daemon down, or /health field absent. PRIMARY gate cannot be evaluated." >&2
           write_soak_summary_and_exit
       fi

       FLOOR_HIT_DELTA=$(( FLOOR_HIT_T24 - floor_hit_cycles_total_start ))
       if (( FLOOR_HIT_DELTA < 0 )); then
           # Counter went backwards — daemon restarted mid-soak. INFRASTRUCTURE
           # gate violated; PRIMARY gate is invalidated by the restart (counter
           # reset to 0).
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_uncollectible_negative_delta_${FLOOR_HIT_DELTA}"
           echo "FAIL: floor_hit_cycles_total_delta=$FLOOR_HIT_DELTA (negative) — daemon restart mid-soak invalidates PRIMARY gate. Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi
       if (( FLOOR_HIT_DELTA > 0 )); then
           SOAK_VERDICT="fail"
           SOAK_FAIL_REASON="soak_primary_gate_floor_hit_cycles_delta_${FLOOR_HIT_DELTA}"
           echo "FAIL: floor_hit_cycles_total_delta=$FLOOR_HIT_DELTA — controller hit floor during the 24h soak (cycle-fidelity counter). Authoring verdict: fail and exiting." >&2
           write_soak_summary_and_exit
       fi
       # FLOOR_HIT_DELTA == 0: PRIMARY gate green. Continue to evaluate
       # SECONDARY (suppression rate) and INFRASTRUCTURE (restart count) gates
       # before the final verdict (per the decision matrix).

       OUT=.planning/phases/201-docsis-aware-ul-congestion-control/soak/$(date -u -d "$soak_start_utc" +%Y%m%dT%H%M%SZ)
       mkdir -p "$OUT"
       ssh cake-shaper "journalctl -u wanctl@spectrum.service --since '$soak_start_utc' --output=cat" > "$OUT/wanctl-spectrum.log"
       # ... use existing soak-monitor.sh + jq pipeline for the suppression-rate stats
       # ... write soak-summary.json including:
       #   floor_hit_cycles_total_start: $floor_hit_cycles_total_start
       #   floor_hit_cycles_total_end:   $FLOOR_HIT_T24
       #   floor_hit_cycles_total_delta: $FLOOR_HIT_DELTA
       #   floor_hit_cycles_total_start_source: $floor_hit_cycles_total_start_source
       ```

    5. **Capture verdict** in `.planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json`:
       ```
       {
         "phase": "201",
         "version": "1.42.0",
         "soak_start_utc": "...",
         "soak_end_utc": "...",
         "soak_duration_s": ...,
         "floor_hit_cycles_total_start": ...,
         "floor_hit_cycles_total_end": ...,
         "floor_hit_cycles_total_delta": 0,
         "floor_hits_during_soak_1hz_secondary": 0,
         "ul_hysteresis_suppression_rate_per_60s": {
           "mean": ...,
           "p50": ...,
           "p95": ...,
           "max": ...
         },
         "headroom_state_distribution": {"AVAILABLE": ..., "EXHAUSTED": ...},
         "cake_aligned_distribution": {"true": ..., "false": ...},
         "rtt_integral_ms_s_p50": ...,
         "rtt_integral_ms_s_p95": ...,
         "rtt_integral_ms_s_max": ...,
         "daemon_restart_count": 0,
         "verdict": "pass"
       }
       ```

       **VALN-06 24h soak watchdog decision matrix (authoritative — operator MUST evaluate every row before authoring `verdict` in soak-summary.json. ALL `pass` conditions must hold conjunctively. ANY single FAIL row makes the verdict `fail`. Ambiguity = FAIL by default; this is a fail-closed contract):**

       | Gate | Condition | Verdict effect if violated | Notes |
       |---|---|---|---|
       | **PRIMARY** (REVIEWS HIGH-5) | `floor_hit_cycles_total_delta == 0` over the 24h window | **FAIL** with reason `soak_primary_gate_floor_hit_cycles_delta_<N>` | Cycle-fidelity 50ms counter; this is the authoritative signal. |
       | **PRIMARY-COLLECTIBILITY** (REVIEWS round-5) | `floor_hit_cycles_total_start` was captured at Step 1.5 AND `/tmp/phase201-soak.env` carries it through to Step 4 AND `floor_hit_cycles_total_delta >= 0` (no daemon restart mid-soak) | **FAIL** with reason `soak_primary_gate_uncollectible_t0_baseline_missing` (Step 1.5 skipped) OR `soak_primary_gate_uncollectible_negative_delta_<N>` (daemon restart mid-soak invalidates the gate) | The PRIMARY gate is only meaningful if the T+0 anchor was actually captured. Operator skipping Step 1.5 OR a mid-soak daemon restart invalidates the entire 24h evidence — fail-closed; do NOT author `verdict: pass` on the assumption that "the counter probably didn't increment." Re-run the soak after capturing T+0 at the start. |
       | **ENV-FILE INTEGRITY** (REVIEWS round-8 + round-9) | `/tmp/phase201-soak.env` passes the strict whitelist validator at Step 4 PRE-source (round-8: only the 3 allowed keys with their per-key value charsets; no magic env vars; no function-export attacks; no malformed entries) AND passes cardinality+completeness checks (round-9: each of the 3 keys appears exactly once; none missing; none duplicated by stale/append residue) | **FAIL** with reason `soak_primary_gate_env_file_contaminated` (whitelist or shape violation) OR `soak_primary_gate_env_file_stale` (duplicate keys: stale data layered over fresh) OR `soak_primary_gate_env_file_incomplete` (missing required key) | The 24h window between Step 1.5 (write) and Step 4 (read) is long enough for the env file to be modified, appended-to, or partially deleted. Strict-mode validation at PRE-source catches all three failure shapes; if any triggers, the file is NOT sourced — soak is authored as FAIL. Round-9 specifically closes the gap where `>>`-append from a previous failed soak attempt would leave stale `soak_start_utc=` or `floor_hit_cycles_total_start=` lines that individually pass round-8 shape but represent multiple incoherent capture sessions. |
       | **SECONDARY** (D-14, NO RELAXATION) | `ul_hysteresis_suppression_rate_per_60s.mean < 5.0` | **FAIL** with reason `soak_secondary_gate_suppression_rate_<value>` | Inherited Phase 200 closure-shape watchdog. |
       | **INFRASTRUCTURE** | `daemon_restart_count == 0` | **FAIL** with reason `soak_infrastructure_daemon_restart_count_<N>` | A daemon restart mid-soak invalidates the counter delta (would reset to 0); restart-count > 0 is itself a regression signal. |
       | **PRIMARY/CROSS-CHECK COHERENCE** | `floor_hit_cycles_total_delta == 0` IFF `floor_hits_during_soak_1hz_secondary == 0` (i.e., they agree) | **FAIL** with reason `soak_primary_secondary_disagreement_counter_<N>_snapshot_<M>` | Disagreement indicates /health-vs-counter drift bug or a counter-increment defect; treated as FAIL not "investigate" — fail-closed. |
       | **DURATION** | `soak_duration_s >= 86_400` (24h minimum) | **FAIL** with reason `soak_duration_short_<N>s` | A short soak has not produced enough evidence to satisfy D-14. |

       **PASS authoring rule:** write `"verdict": "pass"` in soak-summary.json ONLY when every row above is in its non-violated state. If any row violates, write `"verdict": "fail"` with the listed reason string (concatenate multiple reasons with `;` if multiple gates fail). The operator does NOT have discretion to interpret a partial-pass — there is no "PRIMARY pass + SECONDARY fail = soft pass" path. ALL gates must hold.

       **Anti-pattern reminder:** the original Phase 200 closure-shape soak watchdog evaluated only `ul_hysteresis_suppression_rate_per_60s.mean < 5.0`. The cycle-fidelity counter was added by REVIEWS HIGH-5 to close the 1 Hz vs 50ms resolution gap. Demoting the counter to "advisory" by writing `verdict: pass` despite `floor_hit_cycles_total_delta > 0` because suppression rate is fine would re-create the exact fail-OPEN HIGH-5 was designed to prevent. Don't.

    6. **Capture operator-readable summary** in 201-12-SOAK-VERDICT.md mirroring the 201-11 shape (Soak start/end, key stats, decision PASS/FAIL, rollback protocol if FAIL).

    7. **On FAIL**: execute D-10 rollback (same archive Plan 201-11 captured); record rollback in 201-12-SOAK-VERDICT.md; type "soak-fail" + the watchdog metric that failed. Phase 201 closes as `gaps_found` and a follow-up phase is required (mirror Phase 200 closure shape).
  </how-to-verify>
  <resume-signal>
    PASS: type "soak-pass" with the soak-summary.json `floor_hit_cycles_total_delta` (must be 0) AND `ul_hysteresis_suppression_rate_per_60s.mean` (must be < 5.0) to proceed to Task 2 (closeout artifacts). Both numbers are required — operator restating them is an attestation that the AND-gate held.
    FAIL: type "soak-fail" + ALL violated gates from the decision matrix (PRIMARY / SECONDARY / INFRASTRUCTURE / COHERENCE / DURATION — list every one that violated, do NOT pick "the worst"; multiple-gate FAIL is common and operator must surface all of them) + operator's chosen remediation path. If verdict.json contains `;`-separated reasons (multi-gate FAIL), the resume signal must include all of them verbatim.
  </resume-signal>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write 201-VERIFICATION.md, update REQUIREMENTS.md, STATE.md, VALIDATION.md, commit closeout</name>
  <files>
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md,
    .planning/REQUIREMENTS.md,
    .planning/STATE.md,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  </files>
  <read_first>
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md (closure shape mirror — both pass and gaps_found shapes documented there)
    - .planning/REQUIREMENTS.md (VALN-06 row to flip)
    - .planning/STATE.md (current state to update)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md (frontmatter to flip)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
  </read_first>
  <action>
1. **Author `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md`** mirroring Phase 200's structure but reflecting Phase 201's outcome. Required sections:

   ```
   ---
   phase: 201
   slug: docsis-aware-ul-congestion-control
   status: passed | gaps_found | blocked
   closure: <e.g. "valn-06-satisfied">
   inherited_blocking_closed: VALN-06
   nyquist_compliant: true
   wave_0_complete: true
   verified_at: YYYY-MM-DD
   ---

   # Phase 201 — Verification

   ## Inherited blocking closure
   - **VALN-06** (inherited from Phase 200): satisfied via Plan 201-11 canary verdict `pass` with PRIMARY gate `floor_hit_cycles_total_delta_loaded_window == 0` (cycle-fidelity 50ms counter, REVIEWS HIGH-5) AND-coupled with SECONDARY gate `ul_floor_hits_during_load == 0` (1 Hz snapshot, retained for cross-check) — both zero with no disagreement, enforced by the canary script's verdict-decision logic in Plan 08-T3. AND Plan 201-12 24h soak watchdog `pass` with PRIMARY gate `floor_hit_cycles_total_delta == 0` over the 24h window AND SECONDARY gate `ul_hysteresis_suppression_rate_per_60s.mean=<value>` (< 5.0). See `canary/<TS>/verdict.json` and `soak/<TS>/soak-summary.json`.

   ## Per-criterion evidence
   1. Schema accepts new keys + presence flags + ordering: TestPhase201Schema + TestSafe06Phase201KeysKnown + TestDocsisModeValidation green. Plan 201-03.
   2. Canary PRIMARY `floor_hit_cycles_total_delta_loaded_window == 0` AND SECONDARY `ul_floor_hits_during_load == 0`: canary/<TS>/verdict.json (Plan 201-11), with the AND-coupled gate enforced by the canary script in Plan 08-T3. Direct evidence improved upon: Phase 200 canary 20260504T133207Z `ul_floor_hits_during_load: 4` (cycle-fidelity counter not present in v1.41).
   3. 24h soak PRIMARY `floor_hit_cycles_total_delta == 0` AND SECONDARY suppression rate `<5/60s` mean: soak/<TS>/soak-summary.json (Plan 201-12).
   4. Predeploy gate inspects deploy target and aborts on rejected v1.41 keys: scripts/phase201-predeploy-gate.sh; tests/test_phase201_predeploy_gate.py green; live exercise in Plan 201-11.
   5. CHANGELOG + CONFIGURATION.md migration note: greps in Plan 201-06.
   6. Cross-AI review (D-18): 201-09-CODEX-PRE-REVIEW.md + 201-10-CODEX-STOP-TIME-REVIEW.md.

   ## Out of scope (deferred per CONTEXT/RESEARCH; not assessed here)
   - Modem SNMP / DOCSIS HCS counter (D-05; v1.43+).
   - Tighter soak watchdog `<2/60s` (D-14 alternative; v1.43+).
   - DOCSIS-mode auto-tuning of setpoint_mbps.
   - Multi-window integral.
   - ATT cake-primary canary (VALN-05b; cross-milestone).

   ## Closure decision
   <verdict statement matching frontmatter status>
   ```

   For FAIL or BLOCKED outcomes, mirror Phase 200's `closure: deferred-to-phase-XXX` shape and explicitly leave VALN-06 unsatisfied with a follow-up phase recommendation.

2. **Update `.planning/REQUIREMENTS.md`**:
   - Flip VALN-06 checkbox from `[ ]` to `[x]` if PASS.
   - Update the VALN-06 row text from "Blocked in Phase 200 gap closure ... Operator-escalated 2026-05-04: deferred to Phase 201" to "Satisfied in Phase 201 (`docsis-aware-ul-congestion-control`) — canary `pass` with PRIMARY `floor_hit_cycles_total_delta_loaded_window == 0` (cycle-fidelity 50ms counter, REVIEWS HIGH-5) AND SECONDARY `ul_floor_hits_during_load == 0`; 24h soak watchdog `<5/60s` mean (also AND-coupled with counter-delta == 0). See `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md`."
   - On FAIL: leave checkbox `[ ]` and append Phase 201 closure note (gap or block).

3. **Update `.planning/STATE.md`** frontmatter and body:
   - `milestone: v1.42` (or whatever the operator declared at `/gsd-new-milestone` time).
   - `status: Phase 201 closed (passed | gaps_found); VALN-06 <satisfied|deferred>; v1.42 milestone <state>; production on v1.42.0 binary post-canary-pass.`
   - Append to Decisions: `[Phase 201]: Single-phase milestone; D-09 setpoint=12 verified by canary; AUGMENT-not-replace integrating with existing 3-state classifier preserved D-17 byte-identity.`

4. **Update `.planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md`** frontmatter:
   - `status: passed` (or `gaps_found`).
   - `nyquist_compliant: true` (was `false`).
   - `wave_0_complete: true` (was `false`).

5. **Commit closeout**:
   ```
   git add .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/soak/ \
           .planning/REQUIREMENTS.md \
           .planning/STATE.md
   git commit -m "docs(201): close VALN-06 via Phase 201 canary+soak pass"
   ```

   On FAIL/BLOCKED: commit with message `docs(201): close Phase 201 as gaps_found; VALN-06 deferred to <next-phase>` and avoid touching REQUIREMENTS.md to falsely indicate satisfaction.
  </action>
  <acceptance_criteria>
    - `test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` succeeds.
    - `grep -c "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 3.
    - `grep -c "ul_floor_hits_during_load" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 1.
    - `grep -c "nyquist_compliant: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md` returns 1.
    - `grep -c "wave_0_complete: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md` returns 1.
    - On PASS: `grep -c '\\- \\[x\\] \\*\\*VALN-06\\*\\*' .planning/REQUIREMENTS.md` returns 1.
    - On PASS: `grep -c "Satisfied in Phase 201" .planning/REQUIREMENTS.md` returns >= 1.
    - On FAIL: `grep -c "deferred-to-phase-" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 1 (mirror Phase 200 shape).
    - STATE.md last_updated reflects today; status string mentions Phase 201 outcome.
    - No staged but uncommitted changes after the commit step (`git status --porcelain | wc -l` returns 0).
  </acceptance_criteria>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md &amp;&amp; grep -q "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md &amp;&amp; grep -q "nyquist_compliant: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md &amp;&amp; grep -q "wave_0_complete: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md</automated>
  </verify>
  <done>Phase 201 closure artifacts written; VALN-06 status (satisfied or deferred) reflected in REQUIREMENTS.md; STATE.md updated; VALIDATION.md frontmatter flipped; closeout committed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 24h production soak -> wanctl daemon | Live production traffic; soak observes but does not alter. Same trust shape as Phase 198 / Phase 200 soaks. |
| operator-authored verdict -> repository git history | Verdict is captured in committed files; integrity via git. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-53 | Tampering | Soak metric numbers fabricated to clear watchdog | accept | Soak summary cites journalctl + /health captures; reproducible from raw evidence in soak/<TS>/. |
| T-201-54 | Repudiation | VALN-06 closed silently in REQUIREMENTS.md without closure artifact | mitigate | Acceptance gate: 201-VERIFICATION.md must reference verdict.json + soak-summary.json; REQUIREMENTS.md flip cites 201-VERIFICATION.md. |
| T-201-55 | DoS | Soak window itself causes regression (e.g., daemon crash) | accept | Soak is observational; daemon restart count is part of the watchdog metric and gates closure. |
| T-201-56 | Tampering | Frontmatter flipped (nyquist_compliant: true) without actual Wave 0 completion | mitigate | All Wave 0 stubs (Plan 201-02) must have implementation in Plans 03-08 turning them GREEN; flipping the flag without those plans complete is a documentation tampering, caught by reading the test results. |
</threat_model>

<verification>
- Soak summary committed; suppression rate < 5/60s mean; floor hits during soak == 0; daemon restart count == 0.
- 201-VERIFICATION.md authored with full per-criterion evidence pointers.
- REQUIREMENTS.md VALN-06 row updated.
- STATE.md updated.
- VALIDATION.md frontmatter flipped.
- Closeout commit landed.
</verification>

<success_criteria>
- D-14 watchdog satisfied (no relaxation).
- Phase 201 closes with VALN-06 satisfied (or `gaps_found` with explicit deferral if soak fails).
- Closure artifacts mirror Phase 200's verification doc shape.
- Validation strategy formally Nyquist-compliant.
- Cross-AI review trail (Plans 09 + 10) preserved as audit-quality evidence.
</success_criteria>

<output>
The artifact set IS the SUMMARY: 201-VERIFICATION.md + 201-VALIDATION.md (flipped frontmatter) + 201-12-SOAK-VERDICT.md + REQUIREMENTS.md + STATE.md + soak/<TS>/. After commit, Phase 201 (and v1.42 milestone if single-phase) is closed.
</output>
