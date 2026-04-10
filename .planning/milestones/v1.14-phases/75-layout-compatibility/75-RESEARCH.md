# Phase 75: Layout & Compatibility - Research

**Researched:** 2026-03-11
**Domain:** Textual TUI responsive layout, terminal compatibility, color system control
**Confidence:** HIGH

## Summary

This phase adds responsive layout behavior and terminal compatibility to the existing Textual dashboard. The current dashboard (Textual 8.1.1) uses a simple vertical stacking layout within `TabbedContent`. Phase 75 requires: (1) side-by-side WAN panels at >=120 columns, (2) stacked layout below 120, (3) hysteresis to prevent flicker during resize, (4) tmux/SSH compatibility, and (5) `--no-color`/`--256-color` CLI flags.

Textual has no CSS media queries. Responsive behavior must be implemented via `on_resize` event handlers that programmatically switch layout. The `Horizontal` and `Vertical` containers from `textual.containers` provide the building blocks. Textual supports `Pilot.resize_terminal(width, height)` in tests, enabling full coverage of resize behavior. Color control maps to `TEXTUAL_COLOR_SYSTEM` environment variable (values: `"auto"`, `"standard"`, `"256"`, `"truecolor"`) and Rich's `NO_COLOR` convention.

**Primary recommendation:** Use `on_resize` with CSS class toggling to switch between `Horizontal` (wide) and `Vertical` (narrow) containers for WAN panels. Implement hysteresis as a simple timer-based debounce. Map CLI flags to environment variables before `App.run()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LYOT-01 | Adaptive layout: side-by-side WAN panels at >=120 columns | `Horizontal` container + `on_resize` event + CSS class toggle |
| LYOT-02 | Stacked/tabbed layout below 120 columns | `Vertical` container (default) + `on_resize` switches back |
| LYOT-03 | Resize hysteresis prevents layout flicker at breakpoint boundary | Timer-based debounce in `on_resize` handler (e.g., 0.3s delay) |
| LYOT-04 | Dashboard works in tmux and SSH+tmux sessions | Textual works in tmux natively; document TERM settings; test with `run_test()` |
| LYOT-05 | `--no-color` and `--256-color` CLI flags | Map to `TEXTUAL_COLOR_SYSTEM` env var and `NO_COLOR` convention |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| textual | 8.1.1 | TUI framework (already installed) | Already in use; provides containers, resize events, CSS |
| textual.containers | (part of textual) | Horizontal/Vertical layout containers | Standard responsive layout building blocks |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Rich Console ColorSystem | (part of rich) | Color system enum: STANDARD=1, EIGHT_BIT=2, TRUECOLOR=3 | Understanding valid color_system values |

### No New Dependencies

All requirements are satisfied by existing Textual 8.1.1 features. No new libraries needed.

## Architecture Patterns

### Current Layout (Before Phase 75)

```
DashboardApp
  TabbedContent(initial="live")
    TabPane("Live", id="live")
      WanPanelWidget("WAN 1", id="wan-1")     # vertical stack
      SparklinePanelWidget(id="spark-wan-1")
      CycleBudgetGaugeWidget(id="gauge-wan-1")
      WanPanelWidget("WAN 2", id="wan-2")
      SparklinePanelWidget(id="spark-wan-2")
      CycleBudgetGaugeWidget(id="gauge-wan-2")
      SteeringPanelWidget(id="steering")
    TabPane("History", id="history")
      HistoryBrowserWidget(id="history-browser")
  StatusBarWidget(id="status-bar")
```

### Target Layout (After Phase 75)

Wide mode (>=120 columns):
```
DashboardApp
  TabbedContent
    TabPane("Live")
      Horizontal(id="wan-row")           # <-- new container
        Vertical(classes="wan-col")       # <-- WAN 1 column
          WanPanelWidget("WAN 1")
          SparklinePanelWidget
          CycleBudgetGaugeWidget
        Vertical(classes="wan-col")       # <-- WAN 2 column
          WanPanelWidget("WAN 2")
          SparklinePanelWidget
          CycleBudgetGaugeWidget
      SteeringPanelWidget(id="steering")
    TabPane("History")
      HistoryBrowserWidget
  StatusBarWidget
```

Narrow mode (<120 columns): Same as current vertical stack (Horizontal gets `display: none` or switches to Vertical arrangement via CSS class).

### Pattern 1: Responsive Layout via on_resize + CSS Classes

**What:** Handle `Resize` events on the App to detect terminal width changes, then toggle CSS classes that control whether WAN panels are side-by-side or stacked.

**When to use:** Textual has no CSS media queries; this is the standard pattern.

**Implementation approach:**

```python
from textual.containers import Horizontal, Vertical

BREAKPOINT_WIDE = 120

class DashboardApp(App):
    _layout_mode: str = "narrow"  # "wide" or "narrow"
    _resize_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="live"):
            with TabPane("Live", id="live"):
                with Horizontal(id="wan-row"):
                    with Vertical(id="wan-col-1", classes="wan-col"):
                        yield WanPanelWidget("WAN 1", id="wan-1")
                        yield SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
                        yield CycleBudgetGaugeWidget(id="gauge-wan-1")
                    with Vertical(id="wan-col-2", classes="wan-col"):
                        yield WanPanelWidget("WAN 2", id="wan-2")
                        yield SparklinePanelWidget(wan_name="WAN 2", id="spark-wan-2")
                        yield CycleBudgetGaugeWidget(id="gauge-wan-2")
                yield SteeringPanelWidget(id="steering")
            with TabPane("History", id="history"):
                yield HistoryBrowserWidget(...)
        yield StatusBarWidget(id="status-bar")

    def on_resize(self, event: Resize) -> None:
        """Debounced layout switch on terminal resize."""
        self._schedule_layout_check()

    def _schedule_layout_check(self) -> None:
        """Hysteresis: delay layout switch by 0.3s to prevent flicker."""
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(0.3, self._apply_layout)

    def _apply_layout(self) -> None:
        """Switch layout based on current terminal width."""
        width = self.size.width
        new_mode = "wide" if width >= BREAKPOINT_WIDE else "narrow"
        if new_mode == self._layout_mode:
            return
        self._layout_mode = new_mode
        wan_row = self.query_one("#wan-row")
        wan_row.set_class(new_mode == "wide", "wide-layout")
        wan_row.set_class(new_mode == "narrow", "narrow-layout")
```

**CSS approach:**

```css
/* Default: narrow (stacked) */
#wan-row {
    layout: vertical;
    width: 100%;
}

#wan-row.wide-layout {
    layout: horizontal;
}

.wan-col {
    width: 100%;
}

#wan-row.wide-layout .wan-col {
    width: 1fr;
}
```

### Pattern 2: Hysteresis via Timer Debounce

**What:** Prevent rapid layout switching when the user is resizing their terminal near the breakpoint.

**When to use:** Always, when a layout breakpoint exists.

**Key details:**
- Use `App.set_timer(delay, callback)` for debounce (returns Timer that can be stopped)
- 0.3s delay is standard for resize debounce (fast enough to feel responsive, slow enough to avoid flicker)
- Only switch layout when the new mode differs from current mode
- Track current mode in instance variable to avoid redundant switches

### Pattern 3: Color System CLI Flags

**What:** Map `--no-color` and `--256-color` CLI flags to environment variables before Textual starts.

**When to use:** Before `App.run()` is called.

**Implementation:**

```python
# In parse_args():
parser.add_argument("--no-color", action="store_true",
                    help="Disable all color output")
parser.add_argument("--256-color", action="store_true", dest="color_256",
                    help="Use 256-color mode (for limited terminals)")

# In main(), before app.run():
if args.no_color:
    os.environ["NO_COLOR"] = "1"
elif args.color_256:
    os.environ["TEXTUAL_COLOR_SYSTEM"] = "256"
```

**Verified values for `TEXTUAL_COLOR_SYSTEM`:**
- `"auto"` (default) -- auto-detect terminal capability
- `"standard"` -- 16 ANSI colors
- `"256"` -- 256-color palette (8-bit)
- `"truecolor"` -- 16.7M colors (24-bit)

**`NO_COLOR` convention:** Setting `NO_COLOR=1` in env causes Rich Console to set `no_color=True` and `color_system=None`, disabling all color. Textual inherits this via its Rich Console integration.

### Anti-Patterns to Avoid

- **Dynamic mount/unmount for layout switching:** Mounting and unmounting widgets on resize is expensive and loses widget state (sparkline data, panel data). Use CSS class toggling instead.
- **Checking size in compose():** `compose()` runs once at startup. Terminal may resize later. Always use `on_resize` for responsive behavior.
- **Direct style manipulation without classes:** Using `widget.styles.layout = "horizontal"` works but is harder to test and debug than CSS class toggling.
- **Rebuilding widget tree on resize:** Never destroy and recreate widgets just to change layout.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Layout containers | Custom widget arrangement logic | `textual.containers.Horizontal`/`Vertical` | Handles spacing, sizing, overflow correctly |
| Resize debounce | `asyncio.sleep()` + flags | `App.set_timer()` + `Timer.stop()` | Integrates with Textual's event loop; cancellable |
| Color system detection | Manual TERM parsing | `TEXTUAL_COLOR_SYSTEM` env var | Textual/Rich handles all terminal detection |
| NO_COLOR support | Custom color stripping | `NO_COLOR` env var convention | Rich/Textual natively respects this standard |
| Terminal size | `os.get_terminal_size()` | `self.size.width` / `Resize` event | Textual's size tracking is authoritative in fullscreen apps |

## Common Pitfalls

### Pitfall 1: on_resize Fires Before Layout Reflow
**What goes wrong:** Reading widget sizes in `on_resize` returns stale values because layout hasn't been recalculated yet.
**Why it happens:** The event fires before Textual reflows the layout.
**How to avoid:** Use `self.call_after_refresh(callback)` if you need post-layout dimensions. For our case, `self.size.width` (terminal width) is already correct in `on_resize` -- only child widget sizes are stale.
**Warning signs:** Widgets report wrong width immediately after resize.

### Pitfall 2: Widget State Loss on Layout Switch
**What goes wrong:** Sparkline data, panel state, or polling data is lost when switching layouts.
**Why it happens:** Removing and re-mounting widgets resets their state.
**How to avoid:** Never remove/re-mount. Toggle CSS classes on an existing container. All widgets stay in the DOM.
**Warning signs:** Sparkline graphs reset to empty after resize.

### Pitfall 3: tmux Escape Key Delay
**What goes wrong:** Escape key (and sequences using Escape) take >500ms to register in tmux.
**Why it happens:** tmux buffers escape sequences; older tmux defaults `escape-time` to 500ms.
**How to avoid:** Document that users should set `set -sg escape-time 10` in `~/.tmux.conf`. Textual reads `ESCDELAY` env var (default 100ms). tmux 3.5+ defaults to 10ms.
**Warning signs:** Key bindings feel sluggish only inside tmux.

### Pitfall 4: TERM Variable in tmux
**What goes wrong:** Colors degrade or Unicode breaks inside tmux.
**Why it happens:** TERM is set to `screen` (no color info) instead of `tmux-256color` or `screen-256color`.
**How to avoid:** Document recommended tmux settings: `set -g default-terminal "tmux-256color"` and `set -as terminal-features ",xterm-256color:RGB"`.
**Warning signs:** Colors look wrong or sparklines use ASCII fallback in tmux.

### Pitfall 5: SSH COLORTERM Not Forwarded
**What goes wrong:** Dashboard drops to 256-color or standard mode over SSH even though local terminal supports truecolor.
**Why it happens:** SSH doesn't forward `COLORTERM` env var by default.
**How to avoid:** Provide `--256-color` flag as explicit fallback. Document that `COLORTERM=truecolor` can be set on the remote. This is a known limitation -- the `--256-color` flag exists for exactly this case.
**Warning signs:** Colors look slightly different over SSH vs local.

### Pitfall 6: Hysteresis Timer Accumulation
**What goes wrong:** Multiple timers pile up during rapid resizing, causing multiple layout switches.
**Why it happens:** Each `on_resize` call creates a new timer without cancelling the old one.
**How to avoid:** Always stop the previous timer before creating a new one. Store timer reference and call `timer.stop()`.
**Warning signs:** Layout flickers briefly after rapid resize (the exact symptom LYOT-03 prevents).

## Code Examples

### Resize Event Handler with Hysteresis

```python
# Source: Textual docs (events/resize/) + standard debounce pattern
from textual.events import Resize
from textual.timer import Timer

BREAKPOINT = 120
HYSTERESIS_DELAY = 0.3  # seconds

class DashboardApp(App):
    _layout_mode: str = "narrow"
    _resize_timer: Timer | None = None

    def on_resize(self, event: Resize) -> None:
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(
            HYSTERESIS_DELAY, self._apply_layout
        )

    def _apply_layout(self) -> None:
        new_mode = "wide" if self.size.width >= BREAKPOINT else "narrow"
        if new_mode == self._layout_mode:
            return
        self._layout_mode = new_mode
        wan_row = self.query_one("#wan-row")
        wan_row.set_class(new_mode == "wide", "wide-layout")
        wan_row.set_class(new_mode == "narrow", "narrow-layout")
```

### CSS for Layout Switching

```css
/* Narrow mode (default): vertical stacking */
#wan-row {
    layout: vertical;
    width: 100%;
    height: auto;
}

/* Wide mode: side-by-side columns */
#wan-row.wide-layout {
    layout: horizontal;
}

.wan-col {
    width: 100%;
    height: auto;
}

#wan-row.wide-layout .wan-col {
    width: 1fr;
}
```

### CLI Flags for Color Control

```python
# Source: Verified from Textual constants module (TEXTUAL_COLOR_SYSTEM env var)
# and Rich Console (NO_COLOR env var)
import os

def main(argv=None):
    args = parse_args(argv)
    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    elif args.color_256:
        os.environ["TEXTUAL_COLOR_SYSTEM"] = "256"
    config = load_dashboard_config(...)
    app = DashboardApp(config)
    app.run()
```

### Testing Resize with Pilot

```python
# Source: Textual API - Pilot.resize_terminal(width, height)
import asyncio
from wanctl.dashboard.app import DashboardApp
from wanctl.dashboard.config import DashboardConfig

class TestResponsiveLayout:
    def test_wide_layout_at_120_columns(self):
        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                # Allow initial resize event to process
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("wide-layout")
        asyncio.run(_test())

    def test_narrow_layout_below_120_columns(self):
        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("narrow-layout")
        asyncio.run(_test())

    def test_resize_triggers_layout_switch(self):
        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "wide"
                # Resize to narrow
                await pilot.resize_terminal(80, 24)
                await pilot.pause(0.5)  # Wait for hysteresis
                assert app._layout_mode == "narrow"
        asyncio.run(_test())
```

### Testing Color Flags

```python
import os
from unittest.mock import patch
from wanctl.dashboard.app import parse_args

class TestColorFlags:
    def test_no_color_flag_parsed(self):
        args = parse_args(["--no-color"])
        assert args.no_color is True

    def test_256_color_flag_parsed(self):
        args = parse_args(["--256-color"])
        assert args.color_256 is True

    @patch.dict(os.environ, {}, clear=False)
    def test_no_color_sets_env(self):
        # Test that main() sets NO_COLOR before running app
        # (mock App.run to prevent actual app launch)
        ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed terminal layout | Responsive via on_resize | Textual 0.x+ | Must handle manually (no media queries) |
| Terminal color auto-detect only | TEXTUAL_COLOR_SYSTEM env var | Textual 0.50+ | Explicit override for limited terminals |
| tmux escape-time 500ms default | tmux 3.5+ defaults to 10ms | tmux 3.5 (2024) | Much better UX; older tmux needs config |
| Rich NO_COLOR=1 convention | Same, widely adopted | ongoing | Standard way to disable color |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_dashboard/ -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LYOT-01 | Wide layout (>=120 cols) shows side-by-side WAN panels | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestWideLayout -x` | No -- Wave 0 |
| LYOT-02 | Narrow layout (<120 cols) stacks WAN panels vertically | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestNarrowLayout -x` | No -- Wave 0 |
| LYOT-03 | Resize hysteresis prevents flicker | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestHysteresis -x` | No -- Wave 0 |
| LYOT-04 | Works in tmux/SSH+tmux | manual-only | Manual: run in tmux, verify rendering | N/A (manual verification) |
| LYOT-05 | --no-color and --256-color CLI flags | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestColorFlags -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_dashboard/ -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dashboard/test_layout.py` -- covers LYOT-01, LYOT-02, LYOT-03, LYOT-05
- No framework install needed (pytest already configured)
- No new fixtures needed beyond existing conftest.py patterns

## Open Questions

1. **Initial layout on mount**
   - What we know: `on_resize` fires on mount with initial terminal size. `run_test(size=(W, H))` sets initial size.
   - What's unclear: Whether the initial `on_resize` fires early enough to set `wide-layout` class before first render.
   - Recommendation: Call `_apply_layout()` from `on_mount()` as well, to guarantee correct initial layout regardless of event timing. No hysteresis needed for initial apply.

2. **Exact container structure choice**
   - What we know: Two approaches work: (a) Compose with Horizontal container and toggle its CSS `layout` property via classes, (b) compose with a generic Container and toggle between horizontal/vertical layout.
   - What's unclear: Whether toggling `layout` property on a Horizontal container behaves correctly (Horizontal has `layout: horizontal` in DEFAULT_CSS).
   - Recommendation: Use a plain Container (or just set an id on a Vertical) and toggle its layout via CSS classes. This is simpler than fighting the defaults of Horizontal/Vertical containers.

## Sources

### Primary (HIGH confidence)
- Textual 8.1.1 source code (locally installed) -- App.__init__ signature, Resize event, Pilot.resize_terminal, constants module
- Rich Console constructor -- `color_system` accepts `auto|standard|256|truecolor|windows`, `no_color` parameter
- `textual.constants` module -- `TEXTUAL_COLOR_SYSTEM` env var, `ESCAPE_DELAY` from `ESCDELAY`

### Secondary (MEDIUM confidence)
- [Textual Layout Guide](https://textual.textualize.io/guide/layout/) -- Horizontal, Vertical, Grid containers
- [Textual Resize Event](https://textual.textualize.io/events/resize/) -- Event attributes and timing
- [Textual App API](https://textual.textualize.io/api/app/) -- App constructor params
- [NO_COLOR convention](https://no-color.org/) -- Standard for disabling color output

### Tertiary (LOW confidence)
- [tmux+Textual discussion](https://github.com/Textualize/textual/discussions/4003) -- Escape delay and color issues in tmux
- [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ) -- TERM settings, escape-time defaults

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified from locally installed Textual 8.1.1 source
- Architecture: HIGH -- layout containers, resize events, CSS classes all verified in Textual API
- Pitfalls: HIGH -- tmux/SSH issues are well-documented; color system behavior verified locally
- Color flags: HIGH -- `TEXTUAL_COLOR_SYSTEM` and `NO_COLOR` tested locally with live Python

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable domain; Textual 8.x API is mature)
