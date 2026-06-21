---
version: alpha
name: PySmartPack-design
inspiration: linear.app
description: >
  Dark, dense, developer-tool aesthetic for the PySmartPack desktop app.
  Near-black canvas (#0E0E11), four-step surface ladder, hairline borders,
  a single lavender-blue accent (#5E6AD2) reserved for focus / primary CTA /
  active state. No second chromatic accent. Maps Linear's web tokens onto a
  PySide6 + qfluentwidgets (Fluent Design) native window.
---

<!-- LANG-SWITCH --> [中文](./DESIGN.md) · **English**  ·  📖 [README](./README_EN.md) ([中文](./README.md))

# PySmartPack DESIGN.md

Single source of visual truth. The UI layer (`src/pysmartpack/ui/theme.py`)
derives its QSS + qfluentwidgets theme color from these tokens. Do not invent
colors in widgets; pull from `theme.Tokens`.

> The YAML front matter above holds machine-readable tokens (identical across
> languages) for tooling like getdesign.md. Chinese version: [DESIGN.md](./DESIGN.md).

## Color tokens (mapped to Tokens.* in theme.py)

| Token | Hex | Use |
|---|---|---|
| primary | `#5E6AD2` | accent: primary button, active tab, progress fill, focus ring |
| primary_hover | `#828FFF` | hover of primary |
| primary_pressed | `#5E69D1` | pressed/focus tint |
| on_primary | `#FFFFFF` | text on primary |
| canvas | `#0E0E11` | window background (slightly lifted from Linear #010102 for desktop comfort) |
| surface_1 | `#16171A` | cards, panels, tree, log |
| surface_2 | `#1C1D21` | hovered/selected rows, featured panel |
| surface_3 | `#222329` | menus, popovers, inputs |
| hairline | `#2A2C32` | 1px borders, dividers |
| hairline_strong | `#3A3B42` | input border / focus base |
| ink | `#F7F8F8` | primary text, headings |
| ink_muted | `#D0D6E0` | secondary text |
| ink_subtle | `#8A8F98` | tertiary text, captions, disabled labels |
| ink_tertiary | `#62666D` | footnotes, placeholders |
| success | `#27A644` | success state (packaged OK) |
| warning | `#E2A53B` | warnings (dynamic import, missing dep) |
| danger | `#E5484D` | errors / failures |

A11y: body text on canvas/surface meets WCAG AA (>= 4.5:1). Never signal state
by color alone — always pair with an icon or text label (success/warn/error).

## Typography

- UI sans: `Segoe UI` (Windows default) -> `Inter` -> system fallback.
- Mono (logs / code / commands): `Cascadia Code` -> `JetBrains Mono` -> `Consolas` -> monospace.

| Role | Size | Weight |
|---|---|---|
| title | 20px | 600 |
| section | 14px | 600 (UPPERCASE eyebrow, +0.4px tracking) |
| body | 14px | 400 |
| body-sm | 12px | 400 |
| button | 14px | 500 |
| mono | 13px | 400 |

## Shape & spacing

- Base spacing unit: 4px. Scale: 4 / 8 / 12 / 16 / 24 / 32.
- Radius: control 6px, card 10px, pill 9999px.
- Cards: `surface_1` fill + 1px `hairline` border, no drop shadow (depth via surface ladder).
- Focus ring: 1px `primary` border on inputs / focused controls.

## Component mapping (qfluentwidgets)

- Window: `FluentWindow` / `MSFluentWindow`, dark theme, accent = `primary`.
- Primary action: `PrimaryPushButton` (打包 / Package).
- Secondary: `PushButton` (浏览 / 分析).
- Scan results: `TreeWidget` on `surface_1`, checkable items, type icons.
- Options: `RadioButton` groups + `SwitchButton` + `ComboBox` inside `CardWidget`.
- Progress: `ProgressBar` (indeterminate while scanning, determinate while packing).
- Log: read-only `TextEdit` (mono), color-coded lines (info/warn/error).
- Toasts: `InfoBar` for success/error feedback.

## Do / Don't

- Do reserve lavender for focus / primary CTA / active state only.
- Do show every auto-detected item as an editable, checkable row (no silent decisions).
- Don't use a light marketing look; ship dark by default (light theme allowed as toggle).
- Don't add a second bright accent.
