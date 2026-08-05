# ABTP Paper Trading Dashboard UI Details

This file documents the current dashboard UI implemented in `src/abtp/dashboard/paper_server.py`.

Live local URL:

```text
http://127.0.0.1:8765/
```

Launcher:

```text
scripts/open_paper_dashboard.ps1
```

Hidden build marker:

```html
<body data-dashboard-build="dropdown-labels-v1">
```

## Main Visual Style

The dashboard uses a dark crypto-trading terminal style inspired by the reference ABTP mockup.

Primary theme:

| Token | Value | Usage |
|---|---:|---|
| `--bg` | `#06111a` | Main page background |
| `--bg-2` | `#081823` | Secondary dark background |
| `--panel` | `#0b1a26` | Card/panel background |
| `--panel-soft` | `#0e2230` | Softer nested surfaces |
| `--text` | `#e8f1fb` | Main readable text |
| `--muted` | `#91a5b8` | Labels and helper text |
| `--line` | `#1d3444` | Card borders |
| `--line-strong` | `#2b4d62` | Stronger borders |
| `--good` | `#32d583` | Positive/healthy/connected |
| `--warn` | `#ffb84d` | Warning/degraded/trend up |
| `--bad` | `#ff5c5c` | Reject/emergency/error |
| `--accent` | `#2f81ff` | Main blue accent |
| `--accent-2` | `#7c5cff` | Strategy Lab accent |
| `--teal` | `#20c7b5` | Secondary gradient accent |
| `--gold` | `#f2b84b` | BTC/gold highlight |

Background:

```css
radial-gradient(circle at top left, rgba(47, 129, 255, 0.14), transparent 320px),
linear-gradient(180deg, #07131d 0, #06111a 44%, #041018 100%)
```

Card style:

| Property | Value |
|---|---:|
| Border radius | `8px` |
| Border | `1px solid #1d3444` |
| Padding | `14px` |
| Shadow | `0 18px 48px rgba(0, 0, 0, 0.28)` |
| Overflow | `auto` with stable scrollbar gutter |

## Top Header

Header height:

```css
min-height: 92px;
padding: 14px 26px;
position: sticky;
top: 0;
z-index: 10;
```

Header sections from left to right:

1. Brand cluster
   - Logo mark: `A`
   - Title: `ABTP`
   - Subtitle: `AI Backtesting Trading Platform`

2. Pair tile
   - Coin mark: `B`
   - Symbol: `BTC/USDT`
   - Source: `Binance` or `demo`

3. Current Price
   - Main value: `strip_price`
   - Sub value: `strip_change_24h`

4. Market Status
   - Main pill: `strip_signal`
   - Sub value: `Trend Strength: strip_trend_strength`

5. Mode
   - Dropdown id: `ui_mode_select`
   - Dropdown class: `mode-select`
   - Current mode badges under dropdown:
     - `PAPER MODE`
     - `SAFE MODE`
     - `LIVE OFF`

6. Connection
   - Main pill: `strip_connection`
   - Sub value: `strip_latency`

7. Last Updated
   - Main value: `strip_updated`
   - Sub value: `strip_next_check`

8. Notification button
   - Button id: `notification_bell`
   - Count id: `strip_notifications`

## Mode Dropdown

Only these labels should appear in the top Mode dropdown:

```html
<option value="beginner" data-ui-mode="beginner">Beginner</option>
<option value="advanced_trader" data-ui-mode="advanced_trader">Advanced</option>
<option value="strategy_lab" data-ui-mode="strategy_lab">Strategy Lab</option>
```

Do not show `PAPER`, `LAB`, or `Advanced Trader` inside the top dropdown.

The mode state values used by code remain:

| Visible label | Internal value |
|---|---|
| Beginner | `beginner` |
| Advanced | `advanced_trader` |
| Strategy Lab | `strategy_lab` |

## Sidebar

Sidebar width:

```css
grid-template-columns: 178px minmax(0, 1fr);
```

Sidebar is sticky below the header:

```css
top: 92px;
height: calc(100vh - 92px);
```

Sidebar items:

| Icon | Label | Sub label | Action |
|---|---|---|---|
| `DB` | Dashboard | Simple paper view | Beginner mode |
| `AT` | Advanced Trader | Charts and evidence | Advanced mode |
| `SL` | Strategy Lab | Research workspace | Strategy Lab mode |
| `BT` | Backtesting | Embedded panel | Advanced backtest panel |
| `R` | Reports | Paper status | Opens `/paper-report` |
| `AL` | Alerts | Local rules | Advanced alerts panel |
| `LG` | Logs | Activity timeline | Beginner logs panel |
| `ST` | Settings | Paper shell | Readiness/settings area |

Collapse button:

```text
Collapse / Expand
```

## Main Grid

Main content uses a 12-column grid:

```css
main {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  grid-auto-flow: dense;
  gap: 14px;
  padding: 0 16px 18px;
  max-width: 1640px;
  margin: 0 auto;
}
```

Common span classes:

| Class | Grid width |
|---|---:|
| `.span-3` | 3 columns |
| `.span-4` | 4 columns |
| `.span-5` | 5 columns |
| `.span-6` | 6 columns |
| `.span-7` | 7 columns |
| `.span-8` | 8 columns |
| `.span-12` | 12 columns |

## Beginner Dashboard Layout

Beginner mode is the main paper dashboard screen.

Desired first rows:

```text
Row 1:
[Current Recommendation] [Why?] [Portfolio Overview]

Row 2:
[Controls] [Recent Activity]

Row 3:
[AI Explanation full width]
```

Current implemented grid rules:

| Card | Order | Grid columns | Height |
|---|---:|---|---:|
| Current Recommendation | 1 | `1 / 5` | `344px` |
| Why? | 2 | `5 / 8` | `344px` |
| Portfolio Overview | 3 | `8 / 13` | `344px` |
| Controls | 4 | `1 / 8` | `224px` |
| Recent Activity | 5 | `8 / 13` | `224px` |
| AI Explanation | 6 | `1 / 13` | auto, min `206px` |
| Risk & Safety | 8 | span 6 | auto |
| Runtime Telemetry | 9 | span 6 | auto |
| Paper Transactions | 10 | span 6 | auto |
| Readiness Gate | 11 | span 6 | auto |
| Glossary | 11 | span 6 | auto |

Important layout requirements from review:

- Current Recommendation, Why, and Portfolio Overview must line up from the bottom.
- Controls and Recent Activity must sit side by side on the same row.
- Card heights in the same row should match.
- All labels must stay visible.
- Portfolio numbers must fit inside the portfolio cards.
- Avoid large empty right-side space.

## Current Recommendation Card

Visible title:

```text
Current Recommendation
```

Main elements:

| Element | Id/class | Example |
|---|---|---|
| Recommendation label | `beginner_command_label` | `BUY`, `WAIT`, `REJECTED` |
| Confidence pill | `command_confidence` | `CONFIDENCE: 50%` |
| Reason label | static | `Reason` |
| Reason text | `command_reason` | Market explanation |
| Countdown label | static | `Next Check In` |
| Countdown value | `command_next_check` | `10s` |
| Details list | `beginner_command` | Dynamic key/value details |

Visual notes:

- Uses large centered recommendation text.
- Positive label should use green.
- Negative/rejected label should use red.
- Confidence pill is blue-accented.

## Why Card

Visible title:

```text
Why?
```

Main container:

```html
<div class="why-list" id="why_list"></div>
```

Each row includes:

| Element | Purpose |
|---|---|
| Status icon | `OK` or `!` |
| Reason text | Example: `Risk decision: approved` |
| Info marker | Small `i` icon |

Reason tone:

| Tone | Visual |
|---|---|
| Good | Green status |
| Warning | Yellow/orange status |
| Bad/rejected | Red language where applicable |

## Portfolio Overview Card

Visible title:

```text
Portfolio Overview
```

Card grid:

```text
[Portfolio Value] [Cash]
[BTC Holdings]    [Today's P/L]
```

Main elements:

| Label | Id | Example |
|---|---|---|
| Portfolio Value | `strip_equity` | `$10,000.00` |
| Cash | `portfolio_cash_card` | `$9,994.80` |
| BTC Holdings | `portfolio_btc_card` | `0.0500 BTC` |
| BTC value/unrealized | `portfolio_btc_value` | `Unrealized +$0.01` |
| Today's P/L | `strip_today_pnl` | `+$0.00` |
| Today's P/L percent | `portfolio_today_pct` | `0.00%` |

Fit requirements:

- Large money values must not overflow their tile.
- Long decimals should be rounded or compacted before display.
- Each tile should keep stable height.
- Sparkline decorations should not overlap text.

## Controls Card

Visible title:

```text
Controls
```

Main action buttons:

| Button id | Label | Sub label | Tone |
|---|---|---|---|
| `approve` | Approve | Execute Signal | Green |
| `reject` | Reject | Skip Signal | Red |
| `pause` | Pause | Pause Trading | Yellow |
| `emergency` | Emergency Stop | Stop All Activity | Red danger |

Secondary actions:

| Element | Label |
|---|---|
| `resume` | Resume Paper Bot |
| `reset_emergency` | Reset Emergency Stop |
| `/paper-report` link | Daily Report |

Approval reason text:

```html
<p id="approval_reason"></p>
```

Layout requirement:

- In beginner mode, Controls should sit left of Recent Activity.
- Do not make it full width unless explicitly requested again.

## Recent Activity Card

Visible title:

```text
Recent Activity
```

View all button:

```html
<button class="text-link" id="view_all_activity" type="button">View All</button>
```

Timeline item layout:

| Column | Width |
|---|---:|
| Time | `86px` |
| Dot/status | `28px` |
| Main copy | flexible |
| Tag | auto |

Activity tag tones:

| Class | Meaning |
|---|---|
| `.info` | Informational |
| `.action` | User/action event |
| `.system` | System event |
| `.warning` | Warning event |

## AI Explanation Card

Visible title:

```text
AI Explanation
```

Main layout:

```css
grid-template-columns: 112px minmax(0, 1fr);
```

Elements:

| Element | Text/source |
|---|---|
| Bot avatar | `AI` |
| Explanation list | `explanation` |
| Model text | `Model: GPT-4o` |
| Verification pill | `Verified` |
| Confidence | `explanation_confidence` |

## Advanced Mode

Advanced mode shows beginner panels plus advanced trading panels.

Advanced panels include:

| Panel | Purpose |
|---|---|
| Price Chart | Candles, overlays, chart tools, drawings |
| Backtest Summary | Strategy backtest metrics |
| Market | Raw market details |
| Watchlist | Symbols and notes |
| Alerts | Alert rules and triggered alerts |
| Risk & Safety | Risk checks and exchange status |
| Order Book / Market Depth | Bid/ask depth |
| Order Flow / Recent Trades | Recent trade stream |
| Paper Order Ticket | Stage paper orders |
| Open Paper Orders | Existing staged/open orders |
| Trade Journal Analytics | Journal entries and lessons |
| Trader Feedback | Reviewer notes and resolution |
| Paper Position | Position details and close/reduce actions |
| Suggested Paper Trade | Suggested order details |
| Performance | Performance metrics |
| Exit Review | Exit decision details |
| Exports | CSV, report, handoff, evidence links |

## Strategy Lab Mode

Strategy Lab mode shows beginner, advanced context, and strategy research panels.

Main Strategy Lab selector fields:

| Field id | Purpose |
|---|---|
| `lab_strategy` | Strategy selection |
| `lab_symbol` | Symbol selection |
| `lab_timeframe` | Timeframe selection |
| `lab_run_mode` | Run mode |
| `lab_parameter_profile` | Parameter profile |

Strategy Lab panels:

| Panel | Id |
|---|---|
| Strategy Lab | `strategy_lab` |
| Required Evidence | `strategy_lab_evidence` |
| Compare Runs | `strategy_lab_compare` |

## Footer

The status footer uses six columns on desktop:

```css
grid-template-columns: repeat(6, minmax(120px, 1fr));
```

Footer/status items should include:

| Label | Meaning |
|---|---|
| Paper Mode | Simulated trading |
| Data Status | Market/data health |
| Market Source | Binance/demo source |
| Exchange | Connection status |
| Risk Status | Safe mode/risk state |
| Live Trading | Live on/off |
| Refresh | Next refresh/check |
| Version | App version |

## Responsive Behavior

At widths below `1180px`:

- Header becomes a fixed minimum-width grid.
- Main grid keeps 12 columns with `min-width: 1120px`.
- Sidebar uses `196px`.
- Many span classes collapse to smaller spans:
  - `.span-3`, `.span-4`, `.span-5`, `.span-6` become span 3.
  - `.span-7`, `.span-8`, `.span-12` become span 6.

At smaller mobile widths:

- Topbar stacks more aggressively.
- Sidebar becomes less dominant.
- Footer becomes one column.
- Beginner sections remove max-height restrictions.

## Known UI Checks Before Sharing Screenshots

Use this checklist after every UI edit:

1. Open only `http://127.0.0.1:8765/`.
2. Close old preview tabs such as `8766`, `8767`, `8768`, `8769`, `8770`, or `8771`.
3. Press `Ctrl+F5` if Chrome shows an old dropdown.
4. Confirm top Mode dropdown shows:
   - `Beginner`
   - `Advanced`
   - `Strategy Lab`
5. Confirm the first three cards align:
   - Current Recommendation
   - Why?
   - Portfolio Overview
6. Confirm Controls and Recent Activity are on the same row.
7. Confirm no major blank space appears on the right.
8. Confirm portfolio digits fit inside their boxes.
9. Confirm all sidebar labels are readable.
10. Confirm bottom footer/status labels are readable.

## Source Locations

Main UI HTML/CSS/JS:

```text
src/abtp/dashboard/paper_server.py
```

Launcher and stale-page validation:

```text
scripts/open_paper_dashboard.ps1
```

Relevant current line anchors:

| Area | File line |
|---|---|
| Theme tokens | `src/abtp/dashboard/paper_server.py:743` |
| Body build marker | `src/abtp/dashboard/paper_server.py:2368` |
| Mode dropdown labels | `src/abtp/dashboard/paper_server.py:2397` |
| Sidebar navigation | `src/abtp/dashboard/paper_server.py:2423` |
| Beginner card layout CSS | `src/abtp/dashboard/paper_server.py:2193` |
| Launcher stale build checks | `scripts/open_paper_dashboard.ps1:70` |

