---
name: erda-design-system
description: ERDA terminal design tokens, panel chrome, and chart theming. Use for ALL UI work in apps/web — any component, panel, chart, map, or styling change.
---

# ERDA Design System

Source of truth: ERDA_BUILD_SPEC.md §13 (tokens, layout, anti-goals), §12.3, §12.4.
Every UI session loads this skill first. Output from any two sessions must be pixel-consistent.
Iterate with the Playwright screenshot loop (§12.4): render → screenshot → run the checklist in §6 below → fix. Bloomberg-level is 40% data density, 60% typographic discipline.

## 1. TOKENS

Copy-paste this block. Do not restate hex values inline elsewhere — reference the variables.

```css
:root {
  /* §13.1 — the "crude" palette. Exact values, do not adjust. */
  --bg0:  #0C0A07;  /* warm bitumen black — page background. NOT blue-black. */
  --bg1:  #14110C;  /* panel background */
  --line: #262019;  /* hairline borders, grid lines, dividers */

  --gold: #E8A33D;  /* primary accent — black gold */
  --oil:  #3FA66A;  /* discovery / oil wells */
  --gas:  #D64550;  /* gas wells */
  --dry:  #6E6558;  /* dry holes; also muted/tertiary text duty */
  --cyan: #5FB3C9;  /* water / offshore / secondary series */
  --warn: #E5484D;  /* alerts ONLY */

  /* Ink scale (derived, not in spec — --ink from §17 caption color #EDE6DA;
     dimmer steps interpolated toward --bg0. Keep these values verbatim.) */
  --ink:       #EDE6DA;  /* primary text */
  --ink-dim:   #A89E8F;  /* derived — labels, axis text, secondary copy */
  --ink-faint: #6E6558;  /* derived — equals --dry; disabled, placeholders */
}
```

Semantic rules — enforced, not suggested:
- `--gold` sparingly: the `ERDA>` command line and caret, active states, curve M1. If a screenshot has more than a handful of gold elements, it is wrong.
- `--oil` / `--gas` / `--dry` are the industry well-symbol convention: **green oil / red gas / grey dry**. Experts notice this. Never remap.
- Prospectivity ramp is **viridis** (perceptually uniform, colorblind-safe). Use a standard viridis implementation; never hand-pick stops, never substitute a neon ramp.
- `--warn` for alerts only. Not for gas wells, not for negative deltas (use `--gas` for down-ticks per §4a below).
- No colors outside this file. A new color is a spec change, not a styling decision.

## 2. TYPE

- **Space Grotesk** — display and panel titles only. Sparingly.
- **IBM Plex Sans** — all UI copy.
- **IBM Plex Mono** — ALL numerals, everywhere, with `font-variant-numeric: tabular-nums`. A proportional digit anywhere in the terminal is a bug.

```css
.numeric { font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }
```

Density and geometry:
- 8 px spacing grid. Everything snaps to it.
- Data type at 12–13 px. Panel titles 11 px.
- Hairline borders: 1px `--line`. No shadows.
- Border-radius: **0 on panels**, 2 px on chips. Nothing else is rounded.
- Motion ≤ 120 ms; respect `prefers-reduced-motion` (reduce to none).

## 3. PANEL CHROME

Every panel has the same anatomy, top to bottom:

1. **Title bar** — Space Grotesk, uppercase, letterspaced, 11 px, `--ink`; right-aligned **mnemonic tag** (IBM Plex Mono, `--gold`, e.g. `CRV`, `INV`, `DISC`).
2. **Seismic-wiggle divider** — the signature element (§13.1), a thin SVG trace under the title. One signature, everything else disciplined.
3. **Body** — on `--bg1`, inside 1px `--line` border, zero radius.
4. **Freshness badge slot** — top-right of body or title bar; shows source cadence state.
5. **Provenance chip slot** — every number gets one (hover → source, timestamp, URL); chip radius 2 px, mono type.

Wiggle divider — inline SVG, ~1px stroke in `--line`, subtle amplitude, stretches full width:

```html
<svg class="wiggle" width="100%" height="8" viewBox="0 0 240 8"
     preserveAspectRatio="none" aria-hidden="true">
  <path d="M0 4 H28 C32 4 33 1.5 36 1.5 S40 6.5 43 6.5 47 4 50 4 H92
           C96 4 97 2 100 2 S104 6 107 6 111 4 114 4 H164
           C168 4 169 2.5 172 2.5 S176 5.5 179 5.5 183 4 186 4 H240"
        fill="none" stroke="var(--line)" stroke-width="1"/>
</svg>
```

```css
.panel        { background: var(--bg1); border: 1px solid var(--line); border-radius: 0; }
.panel-title  { font-family: 'Space Grotesk', sans-serif; font-size: 11px;
                text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink); }
.panel-mnemo  { font-family: 'IBM Plex Mono', monospace; color: var(--gold); }
.chip         { border: 1px solid var(--line); border-radius: 2px;
                font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-dim); }
```

## 4. CHART THEMING

### 4a. TradingView lightweight-charts — reference config — adapt, keep tokens

```ts
const chart = createChart(el, {
  layout: {
    background: { type: 'solid', color: 'transparent' }, // panel supplies --bg1
    textColor: '#A89E8F',                                // --ink-dim
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: '#262019' },  // --line
    horzLines: { color: '#262019' },  // --line
  },
  rightPriceScale: { borderColor: '#262019' },
  timeScale:       { borderColor: '#262019' },
  crosshair: {
    vertLine: { color: '#6E6558', labelBackgroundColor: '#14110C' },  // --dry / --bg1
    horzLine: { color: '#6E6558', labelBackgroundColor: '#14110C' },
  },
});
// Series conventions:
//   curve M1 / primary line: --gold #E8A33D
//   curve ghosts (1M/1Y ago), secondary series: --cyan #5FB3C9, --dry #6E6558
//   up/down (candles, deltas): upColor --oil #3FA66A, downColor --gas #D64550
```

### 4b. ECharts theme fragment — reference config — adapt, keep tokens

```ts
const erdaTheme = {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'IBM Plex Sans', sans-serif", color: '#A89E8F' }, // --ink-dim
  categoryAxis: {
    axisLine:  { lineStyle: { color: '#262019' } },   // --line
    axisTick:  { lineStyle: { color: '#262019' } },
    axisLabel: { color: '#A89E8F', fontFamily: "'IBM Plex Mono', monospace", fontSize: 11 },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine:  { lineStyle: { color: '#262019' } },
    axisLabel: { color: '#A89E8F', fontFamily: "'IBM Plex Mono', monospace", fontSize: 11 },
    splitLine: { lineStyle: { color: '#262019' } },   // --line
  },
  // series colors: assign per meaning from tokens; no default carousel palette.
};
```

### 4c. deck.gl / MapLibre — reference config — adapt, keep tokens

```ts
// Basemap: CARTO dark-matter (free dark tiles, §13.4).
// Confirm the current style URL at build time; do not hardcode from memory.
const map = new maplibregl.Map({ container, style: CARTO_DARK_MATTER_STYLE_URL });

// Prospectivity raster: viridis ramp (standard implementation), opacity slider.
// Uncertainty: hatch overlay, not a second color ramp.

// Well scatter — token colors as RGB:
const OUTCOME_COLOR = {
  oil: [63, 166, 106],   // --oil #3FA66A
  gas: [214, 69, 80],    // --gas #D64550
  dry: [110, 101, 88],   // --dry #6E6558
};
new ScatterplotLayer({
  id: 'wells',
  getFillColor: (d) => OUTCOME_COLOR[d.outcome],
  // time slider filters by spud_year (§13.4)
});
// GEM infra lines: --cyan family; WDPA overlay: muted, never competing with viridis.
```

## 5. ANTI-GOALS (§13.5, verbatim)

No light mode. No rounded SaaS cards, no gradients, no glassmorphism, no emoji in UI. No spinner longer than 300 ms without a skeleton. Nothing animates that doesn't carry information.

## 6. SELF-CRITIQUE CHECKLIST

Run against every screenshot in the §12.4 loop. All ten must be yes before a UI step is done.

1. Background reads warm bitumen (`--bg0`/`--bg1`), not blue-black or pure #000?
2. Every numeral in IBM Plex Mono with tabular-nums — digit columns align vertically?
3. All borders are 1px `--line` hairlines — no shadows, no gradients, no glow?
4. Zero border-radius on panels; only chips at 2 px?
5. Gold used only for commands, active states, curve M1 — countably few gold elements?
6. Well symbols follow green-oil / red-gas / grey-dry; prospectivity is viridis; `--warn` appears only on alerts?
7. Panel titles are 11 px uppercase letterspaced Space Grotesk with mnemonic tag and wiggle divider present?
8. Layout snaps to the 8 px grid at terminal density — data type 12–13 px, no large idle gaps?
9. Empty/loading states honest — skeletons (never a spinner > 300 ms), no placeholder or fabricated numbers anywhere?
10. Every displayed number has a provenance chip and the panel shows a freshness badge?
