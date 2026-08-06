# ABTP Hybrid Paper Trading Dashboard UI Details

This document defines the complete UI specification for the selected hybrid ABTP dashboard design.

Implementation correction:

- The top Mode dropdown is for trading environment: `Paper Trading` and `Live Trading`.
- The left sidebar is for UI view level: `Beginner`, `Advanced`, and `Strategy Mode`.
- `PAPER MODE` is an active paper-trading environment, not a beginner UI label.

The design rule is:

- Use the **visual structure, styling, spacing, hierarchy, colors, typography, proportions, and card arrangement** from the selected sample UI.
- Use the **features and functional modules** from the existing `paper_dashboard_ui_details.md`.
- Do not remove, hide, replace, or invent project functionality.
- Do not hard-code sample values in production.
- Do not modify trading logic, API contracts, risk logic, recommendation logic, safety gates, paper-trading behavior, audit logging, or route behavior.

Reference image:

```text
imagegen.png
```

Reference canvas:

```text
1536 × 1024 px
```

Existing implementation reference:

```text
src/abtp/dashboard/paper_server.py
```

Local dashboard URL:

```text
http://127.0.0.1:8765/
```

Launcher:

```text
scripts/open_paper_dashboard.ps1
```

---

# 1. Overall Design Objective

The dashboard should look like a professional institutional crypto trading terminal while remaining understandable for beginner users.

The page must combine:

- the polished layout of the selected sample
- the current ABTP paper-trading features
- Beginner, Advanced, and Strategy Lab modes
- live backend-driven values
- clear safety controls
- strong data hierarchy
- responsive behavior
- transparent recommendation reasoning
- paper-trading visibility
- audit and readiness information

The selected UI contains these visible primary regions:

```text
ABTP Application Shell
├── Top Market Header
├── Left Sidebar Navigation
├── Main Dashboard Grid
│   ├── Current Recommendation
│   ├── Why?
│   ├── Portfolio Overview
│   ├── Controls
│   ├── Recent Activity
│   ├── AI Explanation
│   ├── Risk & Safety
│   ├── Runtime Telemetry
│   ├── Paper Transactions
│   ├── Readiness Gate
│   └── Glossary
└── Bottom System Status Bar
```

---

# 2. Core Visual Style

The dashboard uses a dark navy crypto-trading terminal theme.

## Primary theme tokens

```css
:root {
  --bg: #04101a;
  --bg-2: #061522;
  --header-bg: #04111c;
  --sidebar-bg: #061522;

  --panel: #081927;
  --panel-soft: #0b2030;
  --panel-elevated: #0d2434;
  --panel-hover: #102a3d;

  --text: #edf5ff;
  --text-soft: #c7d4e2;
  --muted: #8297aa;
  --muted-2: #60778c;

  --line: #173448;
  --line-soft: rgba(83, 121, 150, 0.28);
  --line-strong: #255675;

  --accent: #2388ff;
  --accent-bright: #339cff;
  --accent-soft: rgba(35, 136, 255, 0.14);

  --good: #2fd078;
  --good-soft: rgba(47, 208, 120, 0.12);

  --warn: #f6ad2f;
  --warn-soft: rgba(246, 173, 47, 0.13);

  --bad: #f0444f;
  --bad-soft: rgba(240, 68, 79, 0.13);

  --orange: #f7931a;
  --gold: #f2b84b;
  --teal: #20c7b5;
  --strategy: #7c5cff;
}
```

## Page background

```css
background:
  radial-gradient(
    circle at 10% 0%,
    rgba(35, 136, 255, 0.10),
    transparent 360px
  ),
  linear-gradient(
    180deg,
    #04111c 0%,
    #061522 48%,
    #03101a 100%
  );
```

## General card style

| Property | Value |
|---|---:|
| Border radius | `9px` |
| Border | `1px solid var(--line)` |
| Background | `var(--panel)` |
| Inner padding | `16px–18px` |
| Shadow | `0 14px 34px rgba(0,0,0,0.24)` |
| Hover border | `var(--line-strong)` |
| Overflow | `hidden` unless the module requires internal scrolling |

Recommendation card:

```css
border-color: rgba(35, 136, 255, 0.88);
box-shadow:
  0 0 0 1px rgba(35, 136, 255, 0.08),
  0 14px 34px rgba(0, 0, 0, 0.24);
```

## Decorative behavior

- Use subtle glows only for active navigation, key status badges, recommendation emphasis, and actionable buttons.
- Do not use heavy glassmorphism.
- Avoid bright gradients across entire cards.
- Keep decoration secondary to data readability.
- Sparklines must remain thin and unobtrusive.
- Avoid large unused blank areas.

---

# 3. Typography

Use a clean professional sans-serif font.

Recommended order:

```css
font-family:
  Inter,
  Geist,
  Manrope,
  "IBM Plex Sans",
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  "Segoe UI",
  sans-serif;
```

## Typography scale

| Element | Font size | Weight | Notes |
|---|---:|---:|---|
| ABTP logo text | `30–34px` | `700` | Tight letter spacing |
| Header primary value | `26–29px` | `650–700` | Tabular figures |
| Card title | `14–15px` | `700` | Uppercase |
| Main recommendation | `72–78px` | `750–800` | Centered |
| Confidence pill | `18–20px` | `650–700` | Uppercase |
| Portfolio metric | `24–28px` | `650–700` | Tabular figures |
| Button primary label | `16–18px` | `700` | Uppercase |
| Body copy | `14–16px` | `400–500` | Line height `1.45–1.55` |
| Supporting text | `11–13px` | `400–600` | Muted |
| Table heading | `10–11px` | `600–700` | Uppercase |
| Footer primary label | `12–13px` | `700` | Uppercase |
| Footer secondary text | `12–13px` | `400–600` | Muted |

Use:

```css
font-variant-numeric: tabular-nums;
```

for:

- prices
- percentages
- balances
- timestamps
- countdown values
- latency
- transaction quantities
- order prices
- version numbers

---

# 4. Global App Shell

The reference image uses a fixed desktop application shell.

## Desktop layout

```text
Viewport: 1536 × 1024 px

Top Header:
  x: 0
  y: 0
  width: 1536px
  height: approximately 91px

Sidebar:
  x: 0
  y: 91px
  width: approximately 184px
  height: approximately 845px

Main Dashboard:
  x: 184px
  y: 91px
  width: approximately 1352px
  height: approximately 845px

Bottom Status Bar:
  x: 0
  y: approximately 936px
  width: 1536px
  height: approximately 88px
```

## Recommended application grid

```css
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 184px minmax(0, 1fr);
  grid-template-rows: 91px minmax(0, 1fr) 88px;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
}
```

## Page behavior

- Header stays sticky at the top.
- Sidebar stays sticky below the header.
- Bottom status bar may be fixed only if the main content receives matching bottom padding.
- The main content must scroll vertically.
- Avoid page-level horizontal scrolling at standard desktop widths.
- Internal tables may scroll horizontally inside their own cards.

---

# 5. Top Header

## Header style

```css
.top-header {
  grid-area: header;
  min-height: 91px;
  display: grid;
  align-items: center;
  background: var(--header-bg);
  border-bottom: 1px solid var(--line-soft);
  padding: 0 24px;
  z-index: 30;
}
```

## Header order

```text
Brand
→ Trading Pair
→ Current Price
→ Market Status
→ Mode
→ Connection
→ Last Updated
→ Notification Bell
```

## Approximate header grid

```css
grid-template-columns:
  190px
  184px
  204px
  210px
  250px
  162px
  156px
  64px;
```

Use `minmax()` in production so values adapt.

## Header separators

- Add a subtle vertical separator between header groups.
- Separator height: `56–62px`
- Separator color: `rgba(117, 151, 177, 0.18)`
- Do not place a separator after the notification button.

---

# 6. Brand Cluster

Visible content:

```text
ABTP
AI BACKTESTING
TRADING PLATFORM
```

## Brand layout

```text
[Geometric ABTP logo] [ABTP]
                      [AI BACKTESTING]
                      [TRADING PLATFORM]
```

## Dimensions

| Element | Size |
|---|---:|
| Logo | `44 × 44px` |
| Logo-text gap | `12px` |
| Brand title | `31–33px` |
| Subtitle | `10–11px` |
| Brand block width | approximately `175px` |

## Behavior

- Clicking the brand navigates to the main dashboard.
- Logo must be an SVG or crisp vector-style component.
- Do not use the old placeholder letters `A` or `AB` if the final logo is available.
- Subtitle remains two lines.
- Logo color is blue.
- Brand title is near-white.

---

# 7. Trading Pair Header Section

Visible content:

```text
BTC/USDT
Binance
```

## Layout

- Orange circular Bitcoin icon
- Pair value beside icon
- Exchange/source below pair
- Pair block vertically centered

## Dimensions

| Element | Size |
|---|---:|
| Coin icon | `42 × 42px` |
| Symbol text | `17–18px` |
| Exchange text | `12–13px` |
| Icon-text gap | `12px` |

## Data mapping

| UI field | Existing source |
|---|---|
| Pair | current market symbol |
| Exchange | Binance or configured market source |
| Coin icon | derived from asset symbol |

## Rules

- Pair must not be hard-coded if symbol selection exists.
- If the active symbol is not BTC, update the icon and label.
- If exchange/source is demo data, show `Demo` or the backend-provided source.
- If the pair is selectable, the control must preserve the same visual footprint.

---

# 8. Current Price Header Section

Visible sample:

```text
Current Price
$68,542.73
+1.28% (24h)
```

## Elements

| Element | Suggested id |
|---|---|
| Price | `strip_price` |
| 24h change | `strip_change_24h` |

## Styling

- Label: muted, `12px`
- Price: `27–29px`, near-white
- Positive 24h change: green
- Negative 24h change: red
- Neutral change: muted gray

## Rules

- Use locale-safe number formatting.
- Preserve precision appropriate to the symbol.
- Do not let large values overflow.
- Use tabular numerals.
- Add an accessible label for currency and percentage.

---

# 9. Market Status Header Section

Visible sample:

```text
Market Status
BULLISH
Trend Strength: 72%
```

## Main status badge

- Green tinted badge
- Leading trend/status icon
- Text: `BULLISH`
- Trailing mini trend icon
- Height: approximately `36px`
- Border radius: `7px`
- Horizontal padding: `12px`

## Suggested fields

| UI field | Existing source |
|---|---|
| Status label | `strip_signal` |
| Trend strength | `strip_trend_strength` |

## State mapping

| State | Color |
|---|---|
| Bullish | green |
| Bearish | red |
| Range Bound | amber |
| Neutral | blue-gray |
| Unknown | muted |

## Rules

- The status is informational.
- It must not imply a guaranteed trade.
- Trend strength is displayed below the badge.
- If trend strength is missing, show `Not calculated`.
- Do not fabricate percentage values.

---

# 10. Mode Section

The selected hybrid UI uses the top mode selector from the existing implementation.

Visible structure:

```text
Mode
[ Beginner ▼ ]
[PAPER MODE] [SAFE MODE] [LIVE OFF]
```

## Mode dropdown

```html
<select id="ui_mode_select" class="mode-select">
  <option value="beginner" data-ui-mode="beginner">Beginner</option>
  <option value="advanced_trader" data-ui-mode="advanced_trader">Advanced</option>
  <option value="strategy_lab" data-ui-mode="strategy_lab">Strategy Lab</option>
</select>
```

## Required labels

Only display:

- Beginner
- Advanced
- Strategy Lab

Do not show:

- PAPER
- LAB
- Advanced Trader

inside the dropdown.

## Supporting badges

Below the dropdown:

- `PAPER MODE`
- `SAFE MODE`
- `LIVE OFF`

## Behavior

| Visible label | Internal value |
|---|---|
| Beginner | `beginner` |
| Advanced | `advanced_trader` |
| Strategy Lab | `strategy_lab` |

## Important rule

`PAPER MODE` is an execution environment.

It must not replace:

- Beginner
- Advanced
- Strategy Lab

---

# 11. Connection Header Section

Visible sample:

```text
Connection
CONNECTED
```

## Suggested fields

| UI field | Existing source |
|---|---|
| Connection status | `strip_connection` |
| Latency/supporting value | `strip_latency` |

## Style

- Green dot
- Green text
- Dark green tinted pill
- Muted latency text below when used

## State mapping

| State | Color |
|---|---|
| Connected | green |
| Degraded | amber |
| Disconnected | red |
| Reconnecting | blue |
| Unknown | muted |

## Rules

- Must reflect actual backend connection status.
- Do not display connected when data is stale.
- Use the same state in header, telemetry, and footer.
- Conflicting status values across cards are not allowed.

---

# 12. Last Updated Header Section

Visible sample:

```text
Last Updated
10:42:31 AM
1s ago
```

## Suggested fields

| UI field | Existing source |
|---|---|
| Absolute update time | `strip_updated` |
| Relative freshness | `strip_next_check` or dedicated freshness field |

## Styling

- Label: muted
- Main time: `15px`, semibold
- Relative age: `12px`, muted

## Rules

- Relative freshness must update safely.
- Do not over-announce every second to screen readers.
- Mark data stale when the configured freshness threshold is exceeded.
- If no update exists, show `Never`.

---

# 13. Notification Button

Suggested ids:

```text
notification_bell
strip_notifications
```

## Visual

- Circular button
- Bell icon
- Blue notification dot/count at top-right
- Approximately `48 × 48px`
- Border: subtle blue-gray
- Hover: lighter navy
- Focus: visible blue ring

## Behavior

- Opens the existing notification or alerts view.
- Dot/count appears only when notifications exist.
- The count must be backend-driven.
- Tooltip: `Notifications`.
- Accessible name must include the unread count.

---

# 14. Sidebar

## Dimensions

```css
.sidebar {
  grid-area: sidebar;
  width: 184px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--line-soft);
  padding: 14px 8px 18px;
}
```

## Sidebar item order

1. Dashboard
2. Advanced Trader
3. Strategy Lab
4. Backtesting
5. Reports
6. Alerts
7. Logs
8. Settings
9. Collapse

## Sidebar labels and sublabels

| Label | Sublabel |
|---|---|
| Dashboard | Simple paper view |
| Advanced Trader | Charts & evidence |
| Strategy Lab | Research workspace |
| Backtesting | Embedded panel |
| Reports | Paper status |
| Alerts | Local rules |
| Logs | Activity timeline |
| Settings | Preferences & API keys |

## Item structure

```text
[Icon] Label
       Sublabel
```

## Item dimensions

| Property | Value |
|---|---:|
| Height | `64–70px` |
| Width | `100%` |
| Horizontal padding | `18–22px` |
| Icon width | `28px` |
| Icon-text gap | `12px` |
| Border radius | `7px` |

## Active item

For Dashboard:

- Blue left border
- Blue icon
- Blue primary label
- Blue-tinted background
- Soft glow
- Sublabel remains muted blue-gray

## Inactive item

- Transparent background
- Light gray primary label
- Muted sublabel
- Hover background: `var(--panel-soft)`
- Focus ring: blue

## Sidebar mapping

| Sidebar item | Action |
|---|---|
| Dashboard | switch to Beginner mode |
| Advanced Trader | switch to Advanced mode |
| Strategy Lab | switch to Strategy Lab mode |
| Backtesting | open/focus embedded Backtesting panel |
| Reports | open `/paper-report` |
| Alerts | open/focus Alerts |
| Logs | open/focus Logs/Activity |
| Settings | open Settings/Readiness area |

## Collapse control

Visible:

```text
Collapse
```

- Icon: double-left chevron
- Position: near sidebar bottom
- Expanded width: `184px`
- Collapsed width: `68–72px`

Collapsed behavior:

- Keep icons
- Hide labels visually
- Preserve accessible names
- Show tooltips on hover/focus
- Main grid expands to use released space

---

# 15. Main Dashboard Grid

The dashboard uses a 12-column responsive grid.

```css
.dashboard-main {
  grid-area: main;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-flow: dense;
  gap: 12px;
  padding: 14px 20px 18px;
  max-width: 1680px;
  width: 100%;
  margin: 0 auto;
}
```

## Reference desktop arrangement

```text
Row 1:
[Current Recommendation] [Why?] [Portfolio Overview]

Row 2:
[Controls                 ] [Recent Activity]

Row 3:
[AI Explanation           ] [Recent Activity continues]

Row 4:
[Risk & Safety] [Runtime Telemetry] [Paper Transactions] [Readiness Gate] [Glossary]
```

## Exact grid placement

| Card | Columns | Approx height |
|---|---|---:|
| Current Recommendation | `1 / 5` | `274px` |
| Why? | `5 / 8` | `274px` |
| Portfolio Overview | `8 / 13` | `274px` |
| Controls | `1 / 8` | `176px` |
| Recent Activity | `8 / 13` | `334px` |
| AI Explanation | `1 / 8` | `148px` |
| Risk & Safety | `1 / 3` | `192px` |
| Runtime Telemetry | `3 / 6` | `192px` |
| Paper Transactions | `6 / 10` | `192px` |
| Readiness Gate | `10 / 12` | `192px` |
| Glossary | `12 / 13` or adjusted wider span | `192px` |

Because the final row has five modules, use a practical responsive column allocation:

```css
.risk-safety       { grid-column: span 2; }
.runtime-telemetry { grid-column: span 3; }
.paper-transactions{ grid-column: span 4; }
.readiness-gate    { grid-column: span 2; }
.glossary          { grid-column: span 1; }
```

At production width, ensure Glossary remains readable. If one column is too narrow, use:

```css
grid-template-columns: repeat(15, minmax(0, 1fr));
```

for the lower module row only, or use a nested grid:

```css
.lower-modules {
  grid-column: 1 / 13;
  display: grid;
  grid-template-columns: 1.2fr 1.3fr 1.7fr 1.1fr 1.3fr;
  gap: 12px;
}
```

The nested-grid approach is preferred.

---

# 16. Current Recommendation Card

Visible title:

```text
CURRENT RECOMMENDATION
```

## Main elements

| Element | Suggested id/class |
|---|---|
| Recommendation label | `beginner_command_label` |
| Confidence | `command_confidence` |
| Reason text | `command_reason` |
| Next check | `command_next_check` |
| Details | `beginner_command` |

## Reference structure

```text
CURRENT RECOMMENDATION

                WAIT

          CONFIDENCE: 82%

──────────────────────────────────

REASON                       NEXT CHECK IN
Market trend is weak.        2m 00s
Volume confirmation missing.
```

## Card layout

- Grid columns: `1 / 5`
- Strong blue border
- Internal padding: `18px`
- Centered primary recommendation section
- Bottom detail area split into 2 columns

## Main recommendation typography

| Element | Style |
|---|---|
| WAIT | `72–78px`, bold, blue |
| Confidence | pill, blue border, `18px` |
| Labels | `11–12px`, uppercase, muted |
| Reason | `14–15px`, near-white |
| Countdown | `20px`, blue |

## Recommendation states

| State | Color |
|---|---|
| BUY | green |
| SELL | red |
| WAIT | blue |
| HOLD | amber |
| BLOCKED | red |
| PAUSED | amber |
| NO DATA | muted |

## Semantic rule

For WAIT:

```text
Confidence means confidence that waiting is currently the correct recommendation.
```

It must not be interpreted as trade-entry confidence.

## Actionability

- WAIT is normally non-actionable.
- Approve must be disabled unless the backend explicitly says the signal is actionable.
- Disabled reason must be available to the user.

---

# 17. Why? Card

Visible title:

```text
WHY?
```

Main container:

```html
<div class="why-list" id="why_list"></div>
```

## Reference reasons

1. Trend confirmation below threshold
2. RSI not in range
3. Volume weak
4. No major news impact
5. Market volatility normal

## Row structure

```text
[Status icon] Reason text [Info icon]
```

## Row dimensions

| Property | Value |
|---|---:|
| Row height | `47–50px` |
| Left icon | `26px` |
| Right info icon | `18px` |
| Row padding | `10px 14px` |
| Divider | `1px solid var(--line-soft)` |

## Tone mapping

| Reason state | Visual |
|---|---|
| Good | green check |
| Warning | amber/orange warning |
| Bad | red error |
| Neutral/info | blue information |

## Info behavior

Clicking the info icon must show available details such as:

- current measured value
- expected threshold/range
- data source
- timestamp
- explanation text

Do not invent details when backend data is unavailable.

---

# 18. Portfolio Overview

Visible title:

```text
PORTFOLIO OVERVIEW
```

Eye/privacy icon appears in the header.

## Card grid

```text
[Portfolio Value] [Cash]
[BTC Holdings]    [Today's P/L]
```

## Metric fields

| Label | Existing id |
|---|---|
| Portfolio Value | `strip_equity` |
| Cash | `portfolio_cash_card` |
| BTC Holdings | `portfolio_btc_card` |
| BTC market/unrealized value | `portfolio_btc_value` |
| Today's P/L | `strip_today_pnl` |
| Today's P/L % | `portfolio_today_pct` |

## Metric tile style

```css
.portfolio-tile {
  min-height: 92px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(10, 31, 47, 0.68);
  padding: 14px 16px;
}
```

## Tile structure

### Portfolio Value

```text
PORTFOLIO VALUE
$10,000.00
[sparkline]
```

### Cash

```text
CASH
$9,800.00
[sparkline]
```

### BTC Holdings

```text
BTC HOLDINGS
0.0034 BTC
≈ $233.44
```

### Today's P/L

```text
TODAY'S P/L
+$12.00
+0.12%
[sparkline]
```

## Sparkline rules

- Use real time-series data only.
- If no history exists, display `No history`.
- Positive: green
- Negative: red
- Neutral: muted
- Sparkline must not overlap text.

## Privacy eye behavior

- Toggles masking for balances and P/L.
- Mask sample: `••••••`
- Privacy state may be local UI state.
- Preserve accessible labels.

## Fit requirements

- Large values must never overflow.
- Use compact notation only when required.
- Use responsive font sizing with `clamp()`.
- Use tabular numerals.

---

# 19. Controls Card

Visible title:

```text
CONTROLS
```

Header right:

```text
Advanced
```

with a sliders/tuning icon.

## Primary control buttons

| Button id | Label | Sublabel | Tone |
|---|---|---|---|
| `approve` | APPROVE | Execute Signal | green |
| `reject` | REJECT | Skip Signal | red |
| `pause` | PAUSE | Pause Trading | amber |
| `emergency` | EMERGENCY STOP | Stop All Activity | red danger |

## Secondary controls

| Element | Label |
|---|---|
| `resume` | Resume Paper Bot |
| `reset_emergency` | Reset Emergency Stop |
| report link | Daily Report |

## Layout

```text
Primary row:
[APPROVE] [REJECT] [PAUSE] [EMERGENCY STOP]

Secondary row:
[Resume Paper Bot] [Reset Emergency Stop] [Daily Report]
```

## Primary button style

| Property | Value |
|---|---:|
| Height | `64–70px` |
| Radius | `8px` |
| Icon circle | `34px` |
| Main label | `15–17px` |
| Sublabel | `12–13px` |
| Gap | `12px` |

## Secondary button style

- Height: `34–38px`
- Dark neutral surface
- Thin border
- Small icon
- Muted text
- Equal-width distribution

## Critical safety rules

- Do not enable Approve when recommendation is WAIT and non-actionable.
- Disabled controls remain visible.
- Display the disabled reason through `approval_reason`.
- Reject, Pause, Resume, Reset Emergency, and Emergency Stop use existing backend endpoints.
- Prevent duplicate submissions.
- Show loading state.
- Show success/error feedback.
- Preserve audit logging.
- Never bypass risk or readiness gates.
- Do not enable live trading.

## Advanced control link

The `Advanced` control must:

- reveal existing advanced controls
- navigate to Advanced mode
- or focus an existing advanced controls panel

Do not create unsupported advanced settings.

---

# 20. Recent Activity

Visible title:

```text
RECENT ACTIVITY
```

View all control:

```html
<button id="view_all_activity" class="text-link" type="button">
  View All
</button>
```

## Timeline structure

```text
Time | Timeline marker | Main content | Badge
```

## Reference entries

| Time | Title | Description | Badge |
|---|---|---|---|
| 10:42:31 AM | Waiting | Market conditions not met | INFO |
| 10:38:12 AM | Signal Rejected | User rejected the signal | ACTION |
| 10:31:45 AM | Market Updated | Market data refreshed | INFO |
| 10:29:18 AM | Portfolio Synced | Balances updated successfully | SYSTEM |
| 10:28:41 AM | System Started | ABTP system initialized | SYSTEM |

## Timeline layout

| Column | Width |
|---|---:|
| Time | `88px` |
| Marker | `30px` |
| Content | flexible |
| Badge | `58–70px` |

## Badge tones

| Badge | Color |
|---|---|
| INFO | blue |
| ACTION | red |
| SYSTEM | green |
| WARNING | amber |
| SAFETY | amber/red according to severity |
| TRADE | green/red according to side/result |

## Rules

- Newest first.
- Use actual event timestamps.
- Do not fabricate activity.
- View All opens existing logs/activity route.
- Loading: skeleton rows.
- Empty: `No recent activity`.
- Error: `Activity could not be loaded`.

---

# 21. AI Explanation Card

Visible title:

```text
AI EXPLANATION
```

## Layout

```text
[Bot Avatar] [Explanation body]
             [Model / Verification] [Confidence]
```

## Reference text

```text
The bot is waiting because the current market doesn’t meet the minimum safety
criteria. The trend is weak and volume is below the required confirmation level.
Entering a trade now would increase risk without a high probability of success.
```

## Existing fields

| Element | Source |
|---|---|
| Explanation | `explanation` |
| Model | configured model name |
| Verification | backend verification field |
| Confidence | `explanation_confidence` |

## Visual dimensions

| Element | Size |
|---|---:|
| Bot avatar area | `90–112px` |
| Avatar circle | `66–76px` |
| Body text | `14–15px` |
| Footer metadata | `11–12px` |

## Rules

- Model name must not be hard-coded.
- Show `Verified` only when supported by real verification state.
- Show explanation confidence only when available.
- Explanation must align with recommendation and reasons.
- Missing explanation: show `Explanation unavailable`.
- Long text wraps naturally.
- Do not truncate without an accessible expansion mechanism.

---

# 22. Risk & Safety Module

Visible title:

```text
RISK & SAFETY
```

## Reference rows

- Safe Mode — Enabled
- Position Size Limit — ≤ 5%
- Max Daily Loss — ≤ 2%
- Drawdown Limit — ≤ 10%
- Exchange — Binance

## Suggested row structure

```text
[status icon] Label [value]
```

## Footer action

```text
Risk Settings >
```

## Data rules

All values must come from existing risk configuration.

Do not hard-code:

- percentage limits
- enabled states
- exchange
- readiness
- safety mode

## State colors

| State | Color |
|---|---|
| Passed/enabled | green |
| Warning/near limit | amber |
| Failed/exceeded | red |
| Unknown | muted |

## Behavior

- `Risk Settings` opens existing settings/readiness area.
- Do not allow edits unless authorization and backend support already exist.
- Any live-trading control remains disabled.

---

# 23. Runtime Telemetry Module

Visible title:

```text
RUNTIME TELEMETRY
```

## Reference fields

- Latency — 42 ms
- Refresh Cadence — 5s
- Data Source — Binance API
- Connection — Connected
- Uptime — 02:14:33
- API Health — Good

## Footer action

```text
View Diagnostics >
```

## Suggested mappings

| Field | Source |
|---|---|
| Latency | `strip_latency` or telemetry field |
| Refresh cadence | configured refresh interval |
| Data source | configured market source |
| Connection | `strip_connection` |
| Uptime | process/service uptime |
| API health | backend health endpoint |

## Rules

- Data must be consistent with header/footer.
- Do not show fake uptime or health.
- Unknown values display `Unavailable`.
- `View Diagnostics` opens existing diagnostics/telemetry panel.

---

# 24. Paper Transactions Module

Visible title:

```text
PAPER TRANSACTIONS
```

## Reference table columns

| Column | Meaning |
|---|---|
| TIME | transaction time |
| SIDE | BUY/SELL |
| QTY (BTC) | quantity |
| PRICE (USDT) | execution price |
| STATUS | order result |

## Reference rows

```text
10:31:12 BUY  0.0010 68,120.50 Filled
10:15:45 SELL 0.0005 67,980.10 Filled
09:48:33 BUY  0.0008 68,010.20 Filled
09:12:07 SELL 0.0006 67,850.30 Filled
```

These values are visual examples only.

## Footer action

```text
View All Transactions >
```

## Style

- Dense table
- Header size: `10px`
- Body size: `11–12px`
- Side:
  - BUY blue/green
  - SELL red
- Filled status:
  - green badge
- Rejected/cancelled:
  - red/gray badge

## Rules

- Use actual paper transaction data.
- Never show live transactions in Beginner paper view unless explicitly labeled.
- Empty state: `No paper transactions`.
- Table must scroll inside card if necessary.
- Keep column headers visible and aligned.
- Quantity and price use tabular numerals.

---

# 25. Readiness Gate Module

Visible title:

```text
READINESS GATE
```

## Reference rows

- Paper-Ready — Ready
- Forward-Testing — Not Ready
- Live-Trading — Not Ready
- Tiny-Staging — Not Ready

## Footer action

```text
View Gate Details >
```

## Status mapping

| Gate state | Color |
|---|---|
| Ready | green |
| Not Ready | amber/red |
| Blocked | red |
| Unknown | muted |

## Rules

- Use actual readiness checks.
- Live Trading must remain blocked unless the backend explicitly reports readiness.
- The UI must not infer readiness from partial conditions.
- Gate details should expose:
  - passed checks
  - failed checks
  - missing evidence
  - last evaluation time

---

# 26. Glossary Module

Visible title:

```text
GLOSSARY
```

## Reference terms

| Term | Meaning |
|---|---|
| RSI | Momentum indicator (0–100) |
| Trend Strength | Strength of current trend |
| Paper Mode | Simulated trading mode |
| Confidence | Reliability of signal (0–100%) |
| Safe Mode | Risk controls enabled |

## Footer action

```text
View All Terms >
```

## Rules

- Keep explanations simple in Beginner mode.
- Use project terminology.
- Advanced mode may show more technical definitions.
- Strategy Lab may include strategy/research terms.
- Glossary content can be static project documentation but must remain accurate.

---

# 27. Bottom System Status Bar

## Layout

Six visible status groups:

1. Paper Mode
2. Data Healthy
3. Latency
4. Binance Connected
5. Risk Status
6. Version

## Reference values

| Primary | Secondary |
|---|---|
| PAPER MODE | Simulated Trading |
| DATA HEALTHY | All Systems Normal |
| LATENCY | 42ms |
| BINANCE CONNECTED | API Connected |
| RISK STATUS | SAFE MODE |
| VERSION | v2.1.0 |

## Footer grid

```css
.system-status-bar {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  min-height: 88px;
  background: #04111c;
  border-top: 1px solid var(--line-soft);
}
```

## Item structure

```text
[Icon] PRIMARY LABEL
       Secondary label
```

## Style

| Property | Value |
|---|---:|
| Icon | `27–30px` |
| Primary | `12–13px`, uppercase |
| Secondary | `12–13px`, muted |
| Divider | vertical, subtle |
| Padding | `18px 30px` |

## Rules

- All status values must be real.
- Footer must agree with header and telemetry.
- Do not fake version, latency, health, risk, or connection.
- Footer must not overlap page content.
- On smaller screens, wrap into multiple rows.

---

# 28. Beginner Mode

Beginner mode is the selected default dashboard.

It must include:

```text
Beginner
├── Current Recommendation
├── Why?
├── Portfolio Overview
├── Controls
├── Recent Activity
├── AI Explanation
├── Risk & Safety
├── Runtime Telemetry
├── Paper Transactions
├── Readiness Gate
├── Glossary
└── Bottom Status Bar
```

## Beginner principles

- Clear language
- Visible safety status
- Simple recommendation
- Direct explanation
- No hidden essential data
- Technical details available but not dominant
- All paper trading actions auditable

---

# 29. Advanced Mode

Advanced mode must include everything from Beginner plus the current advanced feature set.

```text
Advanced
├── Everything in Beginner
├── Price Chart
├── Backtest Summary
├── Market Details
├── Watchlist
├── Alerts
├── Order Book / Market Depth
├── Order Flow / Recent Trades
├── Paper Order Ticket
├── Open Paper Orders
├── Trade Journal Analytics
├── Trader Feedback
├── Paper Position
├── Suggested Paper Trade
├── Performance
├── Exit Review
└── Exports
```

## Advanced panels

| Panel | Purpose |
|---|---|
| Price Chart | candles, overlays, chart tools, drawings |
| Backtest Summary | strategy backtest metrics |
| Market | raw market details |
| Watchlist | symbols and notes |
| Alerts | alert rules and triggered alerts |
| Risk & Safety | risk checks and exchange status |
| Order Book / Market Depth | bid/ask depth |
| Order Flow / Recent Trades | recent trade stream |
| Paper Order Ticket | stage paper orders |
| Open Paper Orders | staged/open orders |
| Trade Journal Analytics | journal entries and lessons |
| Trader Feedback | reviewer notes and resolution |
| Paper Position | position details and close/reduce actions |
| Suggested Paper Trade | proposed order details |
| Performance | performance metrics |
| Exit Review | exit decision details |
| Exports | CSV, report, handoff, evidence links |

Advanced must not remove Beginner cards.

---

# 30. Strategy Lab Mode

Strategy Lab includes everything from Beginner and Advanced plus research and strategy tooling.

## Main selector fields

| Field id | Purpose |
|---|---|
| `lab_strategy` | strategy selection |
| `lab_symbol` | symbol selection |
| `lab_timeframe` | timeframe |
| `lab_run_mode` | run mode |
| `lab_parameter_profile` | parameter profile |

## Main panels

| Panel | Id |
|---|---|
| Strategy Lab | `strategy_lab` |
| Required Evidence | `strategy_lab_evidence` |
| Compare Runs | `strategy_lab_compare` |

## Strategy Lab structure

```text
Strategy Lab
├── Everything in Beginner
├── Everything in Advanced
├── Strategy Selector
├── Symbol Selector
├── Timeframe Selector
├── Run Mode
├── Parameter Profile
├── Strategy Builder
├── Backtesting
├── Required Evidence
├── Compare Runs
├── Evidence Matrix
├── Trader Feedback
├── AI/debug information
├── Readiness proof
└── Exportable research evidence
```

Strategy Lab must not be a separate unrelated UI.

---

# 31. Component Tree

```text
ABTPAppShell
├── TopMarketHeader
│   ├── ProductBrand
│   ├── MarketPairSummary
│   ├── CurrentPriceSummary
│   ├── MarketStatusSummary
│   ├── ModeSelector
│   ├── EnvironmentBadges
│   ├── ConnectionStatus
│   ├── LastUpdatedStatus
│   └── NotificationButton
├── SidebarNavigation
│   ├── SidebarItem[]
│   └── SidebarCollapseButton
├── DashboardMain
│   ├── CurrentRecommendationCard
│   ├── RecommendationReasonsCard
│   ├── PortfolioOverviewCard
│   │   └── PortfolioMetricTile[]
│   ├── ControlsCard
│   │   ├── PrimaryTradingControls
│   │   └── SecondaryTradingControls
│   ├── RecentActivityCard
│   │   └── TimelineItem[]
│   ├── AIExplanationCard
│   └── LowerModulesGrid
│       ├── RiskSafetyCard
│       ├── RuntimeTelemetryCard
│       ├── PaperTransactionsCard
│       ├── ReadinessGateCard
│       └── GlossaryCard
└── SystemStatusBar
    └── SystemStatusItem[]
```

## Reusable primitives

```text
DashboardCard
SectionHeader
MetricTile
StatusBadge
StatusIcon
IconButton
ActionButton
TextLink
Sparkline
Timeline
TimelineItem
CompactTable
KeyValueRow
Tooltip
Popover
Dialog
Toast
Skeleton
EmptyState
ErrorState
```

---

# 32. Suggested Frontend Data Types

Codex should adapt these types to current backend fields rather than forcing backend changes.

```ts
type UiMode = "beginner" | "advanced_trader" | "strategy_lab";

type RecommendationAction =
  | "BUY"
  | "SELL"
  | "WAIT"
  | "HOLD"
  | "BLOCKED"
  | "PAUSED"
  | "NO_DATA";

interface RecommendationReason {
  id: string;
  label: string;
  status: "success" | "warning" | "danger" | "info" | "neutral";
  detail?: string;
  measuredValue?: string | number;
  threshold?: string | number;
  source?: string;
  timestamp?: string;
}

interface DashboardRecommendation {
  action: RecommendationAction;
  confidencePercent?: number;
  confidenceMeaning?: string;
  summaryLines: string[];
  reasons: RecommendationReason[];
  nextCheckAt?: string;
  nextCheckSeconds?: number;
  actionable: boolean;
  approveEnabled: boolean;
  approveDisabledReason?: string;
  generatedAt?: string;
}

interface PortfolioSummary {
  currency: string;
  portfolioValue?: number;
  cashBalance?: number;
  assetSymbol?: string;
  assetQuantity?: number;
  assetMarketValue?: number;
  unrealizedPnl?: number;
  dailyPnl?: number;
  dailyPnlPercent?: number;
  portfolioHistory?: Array<{ timestamp: string; value: number }>;
  cashHistory?: Array<{ timestamp: string; value: number }>;
  pnlHistory?: Array<{ timestamp: string; value: number }>;
  isPaper: boolean;
}

interface ActivityItem {
  id: string;
  timestamp: string;
  title: string;
  description?: string;
  category:
    | "INFO"
    | "ACTION"
    | "SYSTEM"
    | "WARNING"
    | "SAFETY"
    | "TRADE";
  severity?: "success" | "warning" | "danger" | "info" | "neutral";
}

interface AIExplanation {
  text: string;
  modelName?: string;
  verified?: boolean;
  confidencePercent?: number;
  generatedAt?: string;
}

interface RiskSafetyStatus {
  safeMode?: boolean;
  positionSizeLimitPercent?: number;
  maxDailyLossPercent?: number;
  drawdownLimitPercent?: number;
  exchangeName?: string;
}

interface RuntimeTelemetry {
  latencyMs?: number;
  refreshCadenceSeconds?: number;
  dataSource?: string;
  connection?: "connected" | "degraded" | "disconnected" | "unknown";
  uptimeSeconds?: number;
  apiHealth?: "good" | "degraded" | "down" | "unknown";
}

interface PaperTransaction {
  id: string;
  timestamp: string;
  side: "BUY" | "SELL";
  quantity: number;
  symbol: string;
  price: number;
  quoteCurrency: string;
  status: string;
}

interface ReadinessGate {
  id: string;
  label: string;
  status: "ready" | "not_ready" | "blocked" | "unknown";
  details?: string[];
  evaluatedAt?: string;
}

interface SystemStatus {
  executionMode?: "paper" | "live";
  dataHealth?: "healthy" | "degraded" | "down" | "unknown";
  latencyMs?: number;
  exchangeName?: string;
  exchangeConnection?: "connected" | "disconnected" | "degraded";
  riskMode?: string;
  applicationVersion?: string;
}
```

---

# 33. UI States

Every data-driven component must support:

- loading
- ready
- empty
- stale
- partial data
- error
- disconnected
- permission denied
- disabled
- action in progress
- action success
- action failure

## Never display

```text
undefined
null
NaN
[object Object]
blank labels
fake live values
```

## Neutral display values

```text
Unavailable
Waiting for data
Not calculated
No recent activity
No paper transactions
Connection unavailable
No executable signal
Explanation unavailable
No history
```

---

# 34. Interaction Rules

## Mode selector

- Changes active UI mode.
- Does not change execution mode.
- Preserves current route/state where practical.
- Updates sidebar active state.

## Portfolio eye

- Toggles privacy masking.
- Does not change backend data.
- Must remain keyboard accessible.

## Why info buttons

- Open detail popover or expandable row.
- Include measured values and thresholds where available.
- Must not hide essential reason text.

## Approve

- Enabled only when backend allows.
- Confirmation dialog shows:
  - action
  - symbol
  - paper/live status
  - quantity/position size
  - price/order type
  - risk summary
- Uses existing backend endpoint.

## Reject

- Uses existing endpoint.
- Logs action.
- May show existing rejection reason options.

## Pause

- Uses existing paper-bot pause control.
- Changes status consistently across UI.

## Emergency Stop

- Uses existing emergency endpoint.
- Shows persistent stopped state.
- Reset follows current authorization and safety logic.

## Resume Paper Bot

- Uses current resume action.
- Disabled unless bot is paused/stopped in a resumable state.

## Reset Emergency Stop

- Uses current reset action.
- Requires existing authorization/safety checks.

## Daily Report

- Opens `/paper-report`.

## View All Activity

- Opens Logs/activity view.

## Lower-module links

- Risk Settings
- View Diagnostics
- View All Transactions
- View Gate Details
- View All Terms

must navigate to existing pages/panels only.

---

# 35. Accessibility

- Use semantic navigation.
- Use semantic buttons.
- Use heading hierarchy.
- Use lists for timeline and glossary.
- Use table markup for transactions.
- All icon-only controls require accessible labels.
- Visible keyboard focus state.
- Do not rely on color alone.
- Status icon must be paired with text.
- Minimum contrast suitable for dark UI.
- Respect reduced-motion preferences.
- Countdown and freshness updates must not continuously interrupt screen readers.
- Collapsed sidebar items require accessible names and tooltips.

---

# 36. Responsive Behavior

## Large desktop: 1440px and above

- Preserve full reference layout.
- Sidebar expanded.
- Header remains one row.
- First row uses Recommendation, Why, Portfolio.
- Controls and Recent Activity remain side-by-side.
- AI Explanation remains left of Recent Activity.
- Five lower modules remain in a single row when space permits.
- Footer remains six columns.

## Laptop: 1180px–1439px

- Sidebar may collapse.
- Header groups become more compact.
- Lower modules may wrap into two rows.
- Main first row remains readable.
- Avoid horizontal page overflow.

Suggested lower modules:

```text
Risk & Safety | Runtime Telemetry | Paper Transactions
Readiness Gate | Glossary
```

## Tablet: 768px–1179px

- Sidebar becomes compact rail or drawer.
- Header wraps into two rows.
- Main dashboard uses two columns.
- Portfolio remains 2 × 2 inside its card.
- Controls wrap 2 × 2.
- Recent Activity becomes full width.
- Lower modules use 2-column layout.
- Footer wraps into 2 or 3 columns.

## Mobile: below 768px

- Sidebar becomes drawer.
- Header stacks.
- Cards stack in this order:
  1. Recommendation
  2. Why
  3. Portfolio
  4. Controls
  5. AI Explanation
  6. Recent Activity
  7. Risk & Safety
  8. Runtime Telemetry
  9. Paper Transactions
  10. Readiness Gate
  11. Glossary
- Controls use 1 or 2 columns.
- Transactions scroll inside card.
- Footer stacks or uses 2 columns.
- No information may be hidden solely because of screen size.

---

# 37. Implementation Restrictions

Codex must not:

- hard-code screenshot values
- create fake sparklines
- fabricate activity
- fabricate readiness
- fabricate risk limits
- fabricate AI model metadata
- enable live trading
- alter recommendation logic
- alter risk logic
- bypass safety gates
- alter API contracts
- remove existing modules
- hide existing warnings
- rename backend fields without an adapter
- replace backend state with frontend mock state
- create three unrelated dashboards
- use absolute positioning for the main layout
- allow footer overlap
- allow text clipping
- allow values to overflow cards
- allow page-level horizontal scrolling at normal desktop widths

---

# 38. Recommended Implementation Sequence

1. Inspect repository structure.
2. Identify current dashboard HTML, CSS, JS, and API bindings.
3. Identify current Beginner, Advanced, and Strategy Lab modules.
4. Map every visible field to backend state.
5. Report unavailable fields before implementation.
6. Create design tokens.
7. Create reusable card and status primitives.
8. Build app shell.
9. Build header.
10. Build sidebar.
11. Build Recommendation, Why, and Portfolio row.
12. Build Controls and Recent Activity.
13. Build AI Explanation.
14. Build lower modules.
15. Build bottom status bar.
16. Wire all fields to actual backend data.
17. Wire all actions to existing endpoints.
18. Add all UI states.
19. Apply responsive behavior.
20. Apply visual system to Advanced mode.
21. Apply visual system to Strategy Lab.
22. Run tests, type checks, lint, and production build.
23. Capture required screenshots.
24. Produce implementation report.

---

# 39. Acceptance Criteria

The implementation is complete only when:

- The layout visually matches the selected hybrid UI.
- The visual styling follows the sample.
- All features from the existing dashboard details are present.
- Header order matches the specification.
- Mode dropdown shows Beginner, Advanced, Strategy Lab.
- PAPER MODE remains a separate environment badge.
- Sidebar labels and sublabels are visible.
- Current Recommendation, Why, and Portfolio align on row one.
- Controls and Recent Activity align on row two.
- AI Explanation sits beneath Controls.
- Recent Activity spans the right-side height.
- Risk & Safety, Runtime Telemetry, Paper Transactions, Readiness Gate, and Glossary are present.
- Bottom status bar displays six groups.
- All values come from real backend data.
- Missing values show explicit neutral states.
- WAIT is semantically clear.
- Approve is disabled for non-actionable WAIT.
- Existing actions work.
- Audit logging remains intact.
- Live trading remains disabled.
- No text clipping occurs.
- No major empty space appears on the right.
- No cards overlap.
- No portfolio value overflows.
- No footer content is obscured.
- Desktop, laptop, tablet, and mobile layouts remain usable.
- Beginner includes all Beginner modules.
- Advanced includes Beginner plus all Advanced modules.
- Strategy Lab includes Beginner and Advanced plus all Strategy Lab modules.
- Tests pass.
- Type checks pass.
- Lint passes.
- Production build passes.

---

# 40. Required Codex Final Report

Codex must provide:

- files changed
- components created
- components reused
- routes preserved
- backend fields mapped
- unavailable backend fields
- neutral states used
- action endpoints preserved
- disabled-state rules
- safety controls preserved
- mode behavior
- responsive behavior
- accessibility improvements
- tests executed
- test results
- lint result
- type-check result
- production-build result
- remaining limitations

Required screenshots:

- Beginner desktop
- Beginner laptop
- Beginner mobile
- Advanced desktop
- Advanced mobile
- Strategy Lab desktop
- Strategy Lab mobile

---

# 41. Copy-Ready Codex Prompt

```text
Use the attached selected hybrid ABTP dashboard screenshot and the
ABTP_Hybrid_Paper_Dashboard_UI_Details.md file as the complete UI
implementation specification.

The screenshot defines the visual design, layout, hierarchy, spacing, sizing,
colors, typography, card arrangement and component appearance.

The existing paper_dashboard_ui_details.md defines the features and functional
modules that must remain present.

First inspect the complete repository and map every visible field and action to
the real backend/API source. Do not hard-code screenshot values. Do not create
fake charts, activity, telemetry, readiness, risk limits, portfolio values or
AI metadata.

Do not remove, hide, replace or invent features. Do not alter trading logic,
recommendation logic, risk logic, readiness logic, API contracts, routes,
paper-trading behavior, audit logging or safety gates. Do not enable live
trading.

Implement exactly three cumulative views:

Beginner
→ all Beginner modules in the specification

Advanced
→ everything in Beginner plus all existing Advanced Trader modules

Strategy Lab
→ everything in Beginner and Advanced plus all existing Strategy Lab modules

The Mode dropdown must display only:
Beginner
Advanced
Strategy Lab

PAPER MODE, SAFE MODE and LIVE OFF remain separate environment badges.

Build the app shell, header, sidebar, dashboard grid, recommendation, Why,
portfolio, controls, recent activity, AI explanation, Risk & Safety, Runtime
Telemetry, Paper Transactions, Readiness Gate, Glossary and bottom status bar
according to the specification.

Use real backend values. When a field is unavailable, show an explicit neutral
state and report the missing mapping. Preserve all action endpoints, disabled
states, audit behavior and safety controls.

Test desktop, laptop, tablet and mobile layouts. Run tests, lint, type checks
and production build. Provide the required final implementation report and
screenshots.
```
