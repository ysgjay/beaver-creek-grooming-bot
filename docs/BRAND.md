# Chair 0 · Frosted Snow

Chair 0 is the brand; Snow Desk is the product. The lift-terminal symbol has no wordmark attached. Use the resort name in navigation and keep the report, forecast, and cameras as the focus of the product.

## Visual system

| Role | Value |
|---|---|
| Ice background | `#DCEBFA` |
| Frost card | `#F5F9FC` |
| White edge | `#FFFFFF` |
| Ink | `#0C2A4A` |
| Secondary text | `#52677B` |
| Burgundy accent | `#7B1E2E` |
| Burgundy tint (brand accents) | `#F2E6E9` |
| Snow / weather blue | `#376F9B` |
| Expected snow fill | `#C5DFF2` |
| Uncertainty ice tint | `#E5F1FA` |
| Heat-strip maximum | `#88B2D5` |
| Selected navigation tint | `#DCE8F2` |
| Quiet actions | `#365C7D` |
| Divider | `#C3D3E0` |
| Control border | `#7A90A4` |

Outfit is for headings and prominent measurements, IBM Plex Sans for interface text, and IBM Plex Mono for data. The licensed WOFF2 files are self-hosted in `public/brand/fonts/`; each family includes its OFL license. Cards use a white edge and a restrained shadow over a pale ice background. Keep texture in the large logo artwork rather than behind report text.

## Logo files

- `public/icon.svg` and `icon-{180,192,512}.png`: flat burgundy utility icon with an ice background. Use this for the favicon, home screen, and notifications. Its geometry stays inside the maskable safe area.
- `public/brand/logo-utility.svg`: standalone small-format mark.
- `public/brand/logo-outline-burgundy.svg` and `logo-outline-white.svg`: editable outline variants for larger brand applications. Preserve their proportions and allow clear space around the chairs and roof.
- `public/brand/frosted-logo.webp`: approved material artwork, optimized to 640 px. Use it in the top-left home link at 48 px (44 px on narrow phones), and at 160 px on Help. The home link keeps its accessible name; the image itself is decorative.

## Logo anatomy

The mark is a lift terminal seen head-on, with no wordmark and no resort marks.

- **Hood:** a wide trapezoid with rounded corners and a band of three windows (rounded outer corners on the end windows).
- **Bullwheel ring:** the flat ellipse under the hood. It is the "0" in Chair 0, so never fill it or drop it.
- **Column:** one vertical post from the ring's center.
- **Chairs:** two chairs hang from short posts at the hood's outer edges, each with a rounded hanger and a flat seat.
- **Utility geometry:** 320 × 248 viewBox, solid hood with knocked-out windows, 14 px round-capped strokes for ring, posts, and chairs. The app icon scales it 2.5× inside a 1024 square on ice `#DCEBFA`, centered in the maskable safe area.
- **Material version** (`frosted-logo.webp`): the same shape rendered as frosted, slightly translucent ice (pale blue-white with soft highlights and a fine crystalline texture), with burgundy only on the window frames and the chair seats. On a white or ice background it needs no outline. Use it only at 44 px and up; below that use the flat utility mark.

## Interaction and layout

Selected navigation tabs use a flat ice-blue fill and ink text/icon. **No underline, bottom border, or inset bottom shadow.** The header sign-up button uses a light surface with an outline. Routine links, forecast detail headings, calendar controls, and current totals use ink or muted blue. Reserve burgundy for the logo and small brand accents, including primary actions such as form submission and the patrol call. Keep keyboard focus outlines distinct from the selected state. Ordinary text links remain underlined.

The original snowfall charts are part of the identity. Preserve the Today heat strip and the Forecast snow stakes, including ruler ticks, snow drift tops, hatched upper estimates, low-end marks, and model details. Recolor them through the existing tokens without replacing their geometry or interaction. Weekday and MM/DD labels remain in the resort's time zone.

**All snow and weather visualizations use blue or ice shades, never burgundy.** This includes the Today heat strip, forecast stakes and model votes, hourly snow, calendar day/week/month charts and heat cells, uncertainty legends, and radar. `--snow` and `--snow-fill` are separate from the brand `--accent`; data containers locally map the existing chart accent tokens onto the snow palette. The heat strip uses a lighter blue maximum with dark labels throughout, so heavier snow does not turn its numbers white on a pale background. Radar reads `--snow` directly for its generated palette.

Preserve the compact layout: one column and bottom tabs below 900 px, two columns from 900 px, and map-led Today with header tabs from 1200 px. On wide screens the section tabs sit right after the resort name (top left), "Get the morning report" sits alone at the right, and favorite resorts get their own slim row under the header. Desktop spacing is tighter so Today, Forecast, and Calendar fit 1440 × 900. Large frosted artwork belongs in a supporting brand moment, not in place of the report content.

## Reusing the style

For a new page, email header, or sibling product, start from these defaults:

1. **Background:** ice `#DCEBFA` with a soft white radial glow at top left; content sits on white or frost `#F5F9FC` cards with a 1 px white edge, 24 px radius, and the soft navy shadow in `--frost-shadow`.
2. **Type:** Outfit 600 for headings and big numbers, IBM Plex Sans for interface text, IBM Plex Mono for data and small kickers (11 px, 0.05em tracking). Self-host the WOFF2 files with their OFL licenses.
3. **Text color:** ink `#0C2A4A`, secondary `#52677B`. Quiet actions and links use `#365C7D`; ordinary links stay underlined.
4. **Controls:** 44 px minimum touch targets, 12 px radius on buttons and inputs, `#7A90A4` control borders, flat `#DCE8F2` fill for a selected tab, solid `#365C7D` for a pressed segment.
5. **Data:** every snow and weather graphic uses the blue/ice ramp (`#376F9B`, `#C5DFF2`, `#E5F1FA`, `#88B2D5`), never burgundy.
6. **Burgundy `#7B1E2E`:** the logo plus the accent for primary actions, focus, pills, and links (see below). Never in data graphics.
7. **Light mode only.** The app stays on this light palette even when the phone is in dark mode.
8. Write the brand as "Chair 0" with the numeral, and keep "Not affiliated with Vail Resorts" wherever the brand appears with resort content.

## Burgundy in the interface

Decided 11/16: burgundy `#7B1E2E` is the app's accent, replacing the earlier logo-only rule. Besides the logo and icons it appears on primary buttons (email sign-up submit), the patrol card border, keyboard focus outlines, status pills, featured run chips, the Help kicker, plain `<a>` links, and the resort menu's current resort and favorite star. Snow and weather graphics stay blue/ice, and selected tabs, segments, and quiet links stay ink or muted blue.

## Navigation icons

The custom alpine family lives inline in `public/index.html`, shared visually by mobile bottom tabs and desktop header tabs:

- **Today:** sunrise over a snow-capped ridge.
- **Calendar:** bound calendar with a single marked day.
- **Forecast:** three snow stakes with drift tops, echoing the forecast chart.
- **Help:** patrol shield with a cross.

Use a 28 × 28 viewBox, 1.75-unit strokes, and rounded caps and joins. Render at 26 px on mobile and 20 px in the desktop header. Idle icons are slate outlines; the selected icon uses ink with ice `#C5DFF2` in its `nav-ice` shapes. The surrounding selected tab stays flat, without an underline or raised bottom edge. Avoid texture, shadows, or burgundy in these small navigation symbols.

Keep the visible labels, the link's `aria-current="page"`, and the existing generous touch targets. The SVGs are decorative (`aria-hidden="true"`, `focusable="false"`); the link supplies the name and keyboard focus. Both navigation copies must use the same geometry. No image downloads or additional JavaScript are needed.

## Implementation

`public/frost.css` loads after `themes.css` and `app.css`, scoped to `html[data-brand="frosted-snow"]`. The base files retain chart geometry and responsive page structure. `public/sw.js` caches the new stylesheet, utility icons, fonts, and material mark with the app shell. Update its shell version when those resources change. Reduced motion, reduced transparency, keyboard focus, and forced colors have explicit treatments.

The backend, forecast calculations, delivery schedule, opt-in behavior, and resort data are unchanged by this styling update.
