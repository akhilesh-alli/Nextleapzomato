---
name: Obsidian Gourmet Concierge
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#e5bdbe'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#ac8889'
  outline-variant: '#5c3f41'
  surface-tint: '#ffb2b6'
  primary: '#ffb2b6'
  on-primary: '#68001a'
  primary-container: '#ff5169'
  on-primary-container: '#5b0016'
  inverse-primary: '#be0038'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#4edea3'
  on-tertiary: '#003824'
  tertiary-container: '#00a572'
  on-tertiary-container: '#00311f'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdada'
  primary-fixed-dim: '#ffb2b6'
  on-primary-fixed: '#40000d'
  on-primary-fixed-variant: '#920029'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  display-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  caption:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

The design system establishes a high-performance, immersive dining discovery interface tailored for urban food lovers, connoisseurs, and rapid diners. The aesthetic fuses **Dark Minimalist Precision** with **Atmospheric Glassmorphism**, conveying an ambient culinary night-lounge atmosphere combined with high-tech computational intelligence. 

The experience must feel instant, predictive, and sensorial. Users interact not with static catalogs, but with an intelligent culinary concierge that surfaces context-aware recommendations, dish breakdowns, and instant reservation paths. Visual weight is concentrated on rich culinary imagery and precise algorithmic data, supported by ultra-deep obsidian layered surfaces that dissolve UI chrome into the background.

## Colors

The palette operates in strict tonal layers against an ultra-deep obsidian baseline, allowing vibrant culinary tags, ratings, and AI interactions to command immediate attention.

### Base & Structural Neutrals
- **Canvas Base (`#0B0F17`)**: Deep Obsidian baseline for global viewport backgrounds.
- **Card Container (`#131B2E`)**: Deep navy-slate base for elevated cards, modal drawers, and floating panels.
- **Glass Panel Surface (`rgba(255, 255, 255, 0.04)`)**: Frosted interactive translucent planes layered over dark backdrops.
- **Subtle Glass Stroke (`rgba(255, 255, 255, 0.08)`)**: Hairline borders defining translucent structural boundaries.
- **Text Primary (`#F8FAFC`)**: Crisp optical white for high-contrast headlines and critical metrics.
- **Text Muted/Secondary (`#94A3B8`)**: Mid-tone slate for supporting copy, distance markers, and secondary metadata.

### Accents & Semantic Signals
- **Primary Accent (`#FF385C` - Electric Crimson)**: Primary conversion triggers, book-a-table CTAs, and active navigation nodes.
- **Secondary Accent (`#06B6D4` - Neon Cyan)**: AI recommendation badges, taste-match percentages, and semantic generative prompts.
- **Tertiary Accent (`#10B981` - Emerald Green)**: Trust signals, diner ratings (4.5+), open-now indicators, and confirmed reservations.
- **Warning / Tier Accent (`#F59E0B` - Saffron Amber)**: Price tiers (`$$$`), chef specials, limited-seat alerts, and trending heat indicators.

## Typography

The type system blends the contemporary geometric proportions of **Plus Jakarta Sans** for prominent editorial headers and body text with the utilitarian precision of **Inter** for micro-data, metrics, badges, and interface controls.

- **Headlines & Editorial**: Styled with tight negative letter tracking to build an authoritative, modern restaurant guide hierarchy.
- **Labels & System Badges**: Rendered in Inter with positive tracking to optimize legibility on high-density information elements such as AI taste compatibility, table availability, and distance chips.
- **Numerical Metrics**: Rating points, countdown clocks, and currency indices adopt tabular numbering from Inter to avoid optical shifts during real-time filtering.

## Layout & Spacing

The layout model is anchored on an 8pt fluid grid with strict responsiveness for seamless transitions between mobile map-first browsing and multi-pane desktop restaurant consoles.

### Breakpoints & Canvas Bounds
- **Desktop (>= 1280px)**: 12-column layout with 24px gutters, max-width constrained to 1440px or configured as a full-bleed 3-panel split view (Query/Filter Drawer, Dynamic Map, Card Feed).
- **Tablet (768px - 1279px)**: 8-column layout with 20px gutters, adapting search controls into an expandable floating overlay.
- **Mobile (< 768px)**: 4-column layout with 16px gutters and edge margin of 16px. Cards adopt a stacked carousel presentation or full-width sheet cards.

### Internal Spacing Rhythm
- **Micro Spacing (`space-xs`, `space-sm`)**: Applied strictly to tag internals, rating chip layouts, star iconography margins, and input field icons.
- **Block Spacing (`space-md`, `space-lg`, `space-xl`)**: Governs card interior padding, conversational chat speech bubbles, and discovery carousel margins.

## Elevation & Depth

Visual hierarchy does not rely on opaque drop shadows. Depth is achieved via **tonal stratification, frosted glass backdrops, and luminous perimeter rings**.

### 1. Canvas Ground (Level 0)
- Background: Flat `#0B0F17`.
- Used for global application backdrop, map canvas, and structural dividers.

### 2. Surface Card Tier (Level 1)
- Background: `#131B2E`.
- Border: `1px solid rgba(255, 255, 255, 0.05)`.
- Shadow: `0 4px 20px -2px rgba(0, 0, 0, 0.5)`.
- Used for persistent feed items, restaurant cards, and collection blocks.

### 3. Glass Overlay Tier (Level 2)
- Background: `rgba(255, 255, 255, 0.04)` combined with `backdrop-filter: blur(16px) saturate(180%)`.
- Border: `1px solid rgba(255, 255, 255, 0.08)`.
- Shadow: `0 12px 32px -4px rgba(0, 0, 0, 0.6)`.
- Used for floating AI prompt inputs, sticky filter headers, navigation bars, and flyout booking dialogs.

### 4. Interactive Glow Tier (Active State)
- Elements under cursor focus or AI execution project a faint chromatic aura:
  - **Primary Trigger**: `box-shadow: 0 0 24px rgba(255, 56, 92, 0.25)`.
  - **AI Recommendation Engine**: `box-shadow: 0 0 24px rgba(6, 182, 212, 0.2)`.

## Shapes

The design system implements a balanced, rounded profile to balance technical sharpness with lifestyle elegance.

- **Default Radii (`rounded` - 0.5rem / 8px)**: Standard inputs, actionable mini-buttons, and inline data tags.
- **Medium Radii (`rounded-lg` - 1rem / 16px)**: Restaurant presentation cards, map hover cards, modal overlays, and quick-filter pills.
- **Large Radii (`rounded-xl` - 1.5rem / 24px)**: Chat prompt sheets, AI suggestion container blocks, and bottom sheets.
- **Full Pill (`rounded-full`)**: Category pills, rating indicators, voice search trigger buttons, and user avatars.

## Components

### Buttons
- **Primary CTA**: Background `#FF385C`, text `#F8FAFC`, font `label-lg`. On hover, brightness escalates with a subtle red ambient aura (`box-shadow: 0 0 16px rgba(255, 56, 92, 0.35)`).
- **AI Secondary Action**: Glass background (`rgba(6, 182, 212, 0.1)`), text `#06B6D4`, stroke `1px solid rgba(6, 182, 212, 0.3)`. Emits cyan pulse when streaming generated meal suggestions.
- **Ghost/Tertiary Action**: Transparent background, text `#94A3B8`, hover background `rgba(255, 255, 255, 0.06)`, hover text `#F8FAFC`.

### Chips & Badges
- **Rating Chip**: `#10B981` background at 12% opacity, `#10B981` solid text, paired with a star icon. Pill-shaped (`rounded-full`) with `label-sm` weight.
- **Price Indicator**: Background `#131B2E`, text `#F59E0B`, displaying tiered symbols (`$$$`) with inactive symbols dimmed at 30% opacity.
- **AI Match Badge**: Frosted cyan gradient border with inner glow, text `#06B6D4`, prepended by a micro sparkle glyph.

### Restaurant Cards
- Built using the `#131B2E` container with `rounded-lg` corners and a `1px rgba(255, 255, 255, 0.05)` border.
- Features a 16:9 media frame at the top with a subtle bottom gradient feather (`rgba(19, 27, 46, 0)` to `#131B2E`) to fuse the imagery into the card body.
- Content zone contains two tiers: Title (`headline-sm`, `#F8FAFC`) with cuisine subtext (`body-sm`, `#94A3B8`), followed by a bottom metric tray housing the rating badge, wait time, and primary booking trigger.

### Input Fields & AI Prompt Bar
- **Ambient Search / Prompt Field**: Large pill or 16px radius container utilizing `rgba(255, 255, 255, 0.04)` glass surface, `1px rgba(255, 255, 255, 0.08)` border.
- Text input displays `#F8FAFC` with placeholder `#94A3B8`.
- Focus state switches border to `#06B6D4` with `0 0 12px rgba(6, 182, 212, 0.2)` ring.
- Integrated trailing AI spark icon activates real-time generative query translation.

### Checkboxes, Toggles, and Radio Controls
- **Checkboxes & Radios**: Unchecked state shows `1px solid rgba(255, 255, 255, 0.2)` over `#131B2E`. Checked state transitions to `#FF385C` background with white glyph checkmark.
- **Dietary Filter Switches**: Pill toggles that smoothly glide with a `2px` inset and green (`#10B981`) activation fill for vegan/vegetarian preferences.

### AI Suggestion Drawer (Concierge Panel)
- Sticky side or bottom sheet layered with 24px blur glass.
- Employs streaming markdown typings with `#06B6D4` micro-indicator dots during generation.
- Directly references matched menu items with actionable interactive dish tags embedded inside prose text.