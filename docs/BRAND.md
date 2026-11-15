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
| Burgundy tint (snow data) | `#F2E6E9` |
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

## Interaction and layout

Selected navigation tabs use a flat ice-blue fill and ink text/icon. **No underline, bottom border, or inset bottom shadow.** The header sign-up button uses a light surface with an outline. Routine links, forecast detail headings, calendar controls, and current totals use ink or muted blue. Reserve burgundy for the logo, snowfall charts, and primary actions such as form submission and the patrol call. Keep keyboard focus outlines distinct from the selected state. Ordinary text links remain underlined.

The original snowfall charts are part of the identity. Preserve the Today heat strip and the Forecast snow stakes, including ruler ticks, snow drift tops, hatched upper estimates, low-end marks, and model details. Recolor them through the existing tokens without replacing their geometry or interaction. Weekday and MM/DD labels remain in the resort's time zone.

Preserve the compact layout: one column and bottom tabs below 900 px, two columns from 900 px, and map-led Today with header tabs from 1200 px. Desktop spacing is tighter so Today, Forecast, and Calendar fit 1440 × 900. Large frosted artwork belongs in a supporting brand moment, not in place of the report content.

## Implementation

`public/frost.css` loads after `themes.css` and `app.css`, scoped to `html[data-brand="frosted-snow"]`. The base files retain chart geometry and responsive page structure. `public/sw.js` caches the new stylesheet, utility icons, fonts, and material mark with the app shell. Update its shell version when those resources change. Reduced motion, reduced transparency, keyboard focus, and forced colors have explicit treatments.

The backend, forecast calculations, delivery schedule, opt-in behavior, and resort data are unchanged by this styling update.
