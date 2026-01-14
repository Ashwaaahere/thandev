# Thandev Color Palette & Usage Guide

This document catalogs all colors used in the Thandev project and their specific use cases.

## Table of Contents
1. [Theme Colors (CSS Variables)](#theme-colors-css-variables)
2. [Severity Colors](#severity-colors)
3. [Status Colors](#status-colors)
4. [Gradient Colors](#gradient-colors)
5. [PDF Report Colors](#pdf-report-colors)
6. [UI Component Colors](#ui-component-colors)

---

## Theme Colors (CSS Variables)

### Light Mode (`:root`)

#### Base Colors
- **`--bg: #fffaf0`** (Cream/Off-white)
  - **Use Case**: Main page background
  
- **`--fg: #0f172a`** (Slate-900)
  - **Use Case**: Primary text color
  
- **`--muted: #475569`** (Slate-600)
  - **Use Case**: Secondary text, subtext, muted content

#### Brand Colors
- **`--brand: #3b82f6`** (Blue-500)
  - **Use Case**: Primary buttons, links, brand elements
  
- **`--brand-600: #2563eb`** (Blue-600)
  - **Use Case**: Hover states for brand elements
  
- **`--brand-700: #1d4ed8`** (Blue-700)
  - **Use Case**: Active/pressed states, link hover

#### Surface Colors
- **`--surface: #ffffff`** (White)
  - **Use Case**: Cards, panels, elevated surfaces
  
- **`--surface-2: #fff7e6`** (Soft cream)
  - **Use Case**: Alternative panel backgrounds, subtle variations

#### Border Colors
- **`--border: rgba(15,23,42,.10)`** (Slate-900 at 10% opacity)
  - **Use Case**: Card borders, input borders, dividers
  
- **`--hairline: rgba(15,23,42,.08)`** (Slate-900 at 8% opacity)
  - **Use Case**: Subtle dividers, timeline lines, fine separators

#### Shadow Colors
- **`--shadow-1`**: `0 1px 2px rgba(0,0,0,.06), 0 6px 18px rgba(0,0,0,.06)`
  - **Use Case**: Soft shadows for cards (`.shadow-soft`)
  
- **`--shadow-2`**: `0 8px 24px rgba(15,23,42,.08), 0 2px 8px rgba(15,23,42,.06)`
  - **Use Case**: Deeper shadows for elevated elements (`.shadow-deep`)

#### Hero Aurora Colors
- **`--hero-glow`**: Radial gradient with cyan and indigo
  - Colors: `rgba(56,189,248,.45)` (Cyan-400), `rgba(99,102,241,.40)` (Indigo-500)
  - **Use Case**: Hero section background glow effects
  
- **`--orb-cyan: rgba(34,211,238,.38)`** (Cyan-400)
  - **Use Case**: Aurora orb effects in hero sections
  
- **`--orb-indigo: rgba(99,102,241,.36)`** (Indigo-500)
  - **Use Case**: Aurora orb effects in hero sections
  
- **`--orb-emerald: rgba(52,211,153,.32)`** (Emerald-400)
  - **Use Case**: Aurora orb effects in hero sections

#### Accent Colors
- **`--accent-cream`**: Linear gradient `#fffdf7` to `#fff7e6`
  - **Use Case**: Cream accent backgrounds
  
- **`--ring: rgba(37,99,235,.4)`** (Blue-600 at 40% opacity)
  - **Use Case**: Focus rings for interactive elements

#### Selection Colors
- **`--selection-bg: #fde68a`** (Amber-200)
  - **Use Case**: Text selection background
  
- **`--selection-fg: #111827`** (Gray-900)
  - **Use Case**: Text selection foreground

### Dark Mode (`.dark`)

#### Base Colors
- **`--bg: #0b1220`** (Dark blue-gray)
  - **Use Case**: Main page background in dark mode
  
- **`--fg: #e5e7eb`** (Gray-200)
  - **Use Case**: Primary text color in dark mode
  
- **`--muted: #94a3b8`** (Slate-400)
  - **Use Case**: Secondary text in dark mode

#### Brand Colors (Dark Mode)
- **`--brand: #7dd3fc`** (Sky-300)
  - **Use Case**: Primary buttons/links in dark mode
  
- **`--brand-600: #22d3ee`** (Cyan-400)
  - **Use Case**: Hover states in dark mode
  
- **`--brand-700: #06b6d4`** (Cyan-500)
  - **Use Case**: Active states in dark mode

#### Surface Colors (Dark Mode)
- **`--surface: rgba(255,255,255,.06)`**
  - **Use Case**: Cards/panels in dark mode
  
- **`--surface-2: rgba(255,255,255,.08)`**
  - **Use Case**: Alternative surfaces in dark mode

#### Border Colors (Dark Mode)
- **`--border: rgba(255,255,255,.10)`**
  - **Use Case**: Borders in dark mode
  
- **`--hairline: rgba(255,255,255,.08)`**
  - **Use Case**: Subtle dividers in dark mode

#### Shadows (Dark Mode)
- **`--shadow-1`**: `0 1px 2px rgba(0,0,0,.35), 0 10px 24px rgba(0,0,0,.28)`
- **`--shadow-2`**: `0 14px 36px rgba(0,0,0,.35), 0 4px 10px rgba(0,0,0,.25)`

#### Hero Aurora (Dark Mode)
- **`--hero-glow`**: Reduced opacity versions of cyan/indigo
- **`--orb-cyan: rgba(34,211,238,.20)`**
- **`--orb-indigo: rgba(99,102,241,.18)`**
- **`--orb-emerald: rgba(52,211,153,.18)`**

#### Selection (Dark Mode)
- **`--selection-bg: #1f2937`** (Gray-800)
- **`--selection-fg: #e5e7eb`** (Gray-200)

---

## Severity Colors

### Frontend UI Severity Colors

#### Critical
- **Light Mode**: `text-red-600 bg-red-100`
- **Dark Mode**: `dark:text-red-400 dark:bg-red-900/20`
- **Alternative**: `bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30`
- **Badge Style**: `bg-red-900/40 text-red-200 border-red-500/50`
- **Use Case**: Critical vulnerability badges, severity indicators

#### High
- **Light Mode**: `text-orange-600 bg-orange-100`
- **Dark Mode**: `dark:text-orange-400 dark:bg-orange-900/20`
- **Alternative**: `bg-orange-500/20 text-orange-600 dark:text-orange-400 border border-orange-500/30`
- **Badge Style**: `bg-orange-900/40 text-orange-200 border-orange-500/50`
- **Use Case**: High severity vulnerability badges

#### Medium
- **Light Mode**: `text-yellow-600 bg-yellow-100`
- **Dark Mode**: `dark:text-yellow-400 dark:bg-yellow-900/20`
- **Alternative**: `bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 border border-yellow-500/30`
- **Badge Style**: `bg-yellow-900/40 text-yellow-200 border-yellow-500/50`
- **Use Case**: Medium severity vulnerability badges

#### Low
- **Light Mode**: `text-green-600 bg-green-100` OR `text-blue-600 bg-blue-100`
- **Dark Mode**: `dark:text-green-400 dark:bg-green-900/20` OR `dark:text-blue-400 dark:bg-blue-900/20`
- **Alternative**: `bg-green-500/20 text-green-600 dark:text-green-400 border border-green-500/30`
- **Badge Style**: `bg-green-900/40 text-green-200 border-green-500/50`
- **Use Case**: Low severity vulnerability badges

#### Info
- **Light Mode**: `text-slate-600 bg-slate-100` OR `text-gray-600 bg-gray-100`
- **Dark Mode**: `dark:text-slate-400 dark:bg-slate-900/20` OR `dark:text-gray-400 dark:bg-gray-900/20`
- **Badge Style**: `bg-slate-800/40 text-slate-200 border-slate-600/50`
- **Use Case**: Informational badges, neutral severity indicators

---

## Status Colors

### Scan/Job Status Colors

#### Completed
- **Light Mode**: `text-green-600`
- **Dark Mode**: `dark:text-green-400`
- **Badge Style**: `bg-green-900/40 text-green-200 border-green-500/50`
- **Use Case**: Completed scan status badges, success indicators

#### Running
- **Light Mode**: `text-blue-600`
- **Dark Mode**: `dark:text-blue-400`
- **Badge Style**: `bg-blue-900/40 text-blue-200 border-blue-500/50`
- **Use Case**: Active/running scan status

#### Failed/Error
- **Light Mode**: `text-red-600`
- **Dark Mode**: `dark:text-red-400`
- **Badge Style**: `bg-red-900/40 text-red-200 border-red-500/50`
- **Use Case**: Failed scan status, error states

#### Queued/Pending
- **Light Mode**: `text-yellow-600`
- **Dark Mode**: `dark:text-yellow-400`
- **Badge Style**: `bg-yellow-900/40 text-yellow-200 border-yellow-500/50` OR `bg-slate-800/40 text-slate-200 border-slate-600/50`
- **Use Case**: Queued/pending scan status

### Plan/Level Colors

#### Advanced
- **Badge Style**: `bg-purple-900/40 text-purple-200 border-purple-500/50`
- **Use Case**: Advanced plan level indicators

#### Pro
- **Badge Style**: `bg-indigo-900/40 text-indigo-200 border-indigo-500/50`
- **Use Case**: Pro plan level indicators

#### Basic
- **Badge Style**: `bg-blue-900/40 text-blue-200 border-blue-500/50`
- **Use Case**: Basic plan level indicators

---

## Gradient Colors

### Hero Gradients
- **Holographic Title**: `linear-gradient(92deg, #60a5fa 0%, #a78bfa 35%, #22d3ee 70%, #60a5fa 100%)`
  - Colors: Blue-400 → Purple-400 → Cyan-400 → Blue-400
  - **Use Case**: Futuristic title text effects (`.title-future`)

- **Cyan to Indigo**: `from-cyan-400 to-indigo-500`
  - **Use Case**: Loading bars, progress indicators, accent gradients

- **Cyan to Indigo (Text)**: `bg-gradient-to-r from-cyan-400 to-indigo-500 bg-clip-text text-transparent`
  - **Use Case**: Gradient text effects

### Button Gradients
- **Neon Glow**: `radial-gradient(60% 80% at 50% 50%, rgba(56,189,248,.45), transparent 70%)`
  - **Use Case**: Neon button effects (`.btn-neon`)

### Card Gradients
- **Surface Gradient**: `linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)`
  - **Use Case**: Card backgrounds with subtle depth

- **Featured Card**: `linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%)`
  - **Use Case**: Featured/highlighted cards

### Background Gradients
- **Band Gradient**: `linear-gradient(180deg, color-mix(in oklab, var(--bg) 90%, white 10%), var(--bg))`
  - **Use Case**: Section background bands

---

## PDF Report Colors

### Base Colors
- **`COLOR_PAGE_BG`**: `colors.white`
  - **Use Case**: PDF page background

- **`COLOR_TEXT_PRIMARY`**: `#0f172a` (Slate-900)
  - **Use Case**: Primary text in PDF reports

- **`COLOR_TEXT_MUTED`**: `#475569` (Slate-600)
  - **Use Case**: Secondary/muted text in PDF

- **`COLOR_ACCENT`**: `#4f46e5` (Indigo-600)
  - **Use Case**: Thandev brand color in PDFs

- **`COLOR_HEADER_BG`**: `#4f46e5` (Indigo-600)
  - **Use Case**: PDF header backgrounds

- **`COLOR_LABEL_BG`**: `#f1f5f9` (Slate-100)
  - **Use Case**: Label backgrounds in PDF tables

- **`COLOR_ROW_ALT`**: `#f8fafc` (Slate-50)
  - **Use Case**: Alternating row backgrounds

- **`COLOR_CARD_BG`**: `#f8fafc` (Slate-50)
  - **Use Case**: Card backgrounds in PDF

### PDF Severity Colors
- **Critical**: `#dc2626` (Red-600)
  - Background: `#dc2626`, Text: White
  
- **High**: `#ea580c` (Orange-600)
  - Background: `#ea580c`, Text: White
  
- **Medium**: `#ca8a04` (Yellow-600)
  - Background: `#fef3c7` (Amber-100), Text: `#78350f` (Amber-900)
  
- **Low**: `#16a34a` (Green-600)
  - Background: `#dcfce7` (Green-100), Text: `#14532d` (Green-900)
  
- **Info**: `#64748b` (Slate-500)
  - Background: `#e2e8f0` (Slate-200), Text: `#1e293b` (Slate-800)

### PDF Status Colors
- **Completed**: `#16a34a` (Green-600)
- **Failed/Error**: `#dc2626` (Red-600)
- **Running/Pending/Queued**: `#ca8a04` (Yellow-600)

---

## UI Component Colors

### Live/Active Indicators
- **Live Dot**: `#ef4444` (Red-500)
  - **Use Case**: Live status indicators with pulse animation

- **Timeline Pin**: `#f59e0b` (Amber-500)
  - **Use Case**: Timeline item markers

### Score Colors
- **High Score (≥80)**: `text-green-600 dark:text-green-400`
- **Medium Score (≥60)**: `text-yellow-600 dark:text-yellow-400`
- **Low Score (<60)**: `text-red-600 dark:text-red-400`

### Special UI Elements
- **404 Page Gradient**: `from-cyan-400 to-indigo-500`
- **Loading Spinner**: `border-cyan-200 dark:border-cyan-800 border-t-cyan-500 dark:border-t-cyan-400`
- **Progress Bar**: `bg-gradient-to-r from-cyan-500 to-indigo-500`

### Badge Colors
- **Live Badge**: `rgba(16,185,129,.08)` background, `#10b981` text (Green-500)
- **Soon Pill**: Uses `var(--muted)` with border

### Error States
- **Error Boundary**: Red gradient backgrounds with red borders
  - Light: `from-red-50/50 to-red-100/30`, `border-red-200/50`
  - Dark: `from-red-950/40 to-red-900/20`, `border-red-800/50`

---

## Color Usage Patterns

### Severity Badge Pattern
Most severity badges follow this pattern:
- Light mode: `text-{color}-600 bg-{color}-100`
- Dark mode: `dark:text-{color}-400 dark:bg-{color}-900/20`
- Alternative: `bg-{color}-500/20 text-{color}-600 dark:text-{color}-400 border border-{color}-500/30`

### Status Badge Pattern
Status badges typically use:
- Light mode: `text-{color}-600`
- Dark mode: `dark:text-{color}-400`
- Or: `bg-{color}-900/40 text-{color}-200 border-{color}-500/50`

### Gradient Pattern
Common gradient pattern for futuristic effects:
- `from-cyan-400 to-indigo-500` or variations with purple/emerald

---

## Notes

1. **Consistency**: Severity colors are consistent across frontend components but may have slight variations in opacity/brightness for different contexts.

2. **Dark Mode**: All colors have dark mode variants using Tailwind's `dark:` prefix or CSS variables that adapt automatically.

3. **Accessibility**: Colors are chosen to meet contrast requirements for text readability.

4. **Brand Identity**: The primary brand color is blue (`#3b82f6` in light, `#7dd3fc` in dark), with indigo (`#4f46e5`) used in PDF reports.

5. **Futuristic Theme**: The color palette emphasizes cyan, indigo, and emerald gradients for a modern, tech-forward aesthetic.
