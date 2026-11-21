# 0xSnow / Brand specification

Version 1.1 · 21 November 2026

## Brand foundation

**Company:** 0xSnow. Ski-resort snow forecasting, snow data, grooming reports and resort information.

**Personality:** simple, technically considered, frosty, calm and useful.

**Promise:** Mountain information, made clear.

The brand helps someone answer what fell, what is groomed and what comes next. Its credibility comes from readable numbers, visible sources and honest uncertainty. The primary symbol combines a numeral zero, a snow gauge and a snowline.

### Working slogan

**Glacial Precision** is the candidate slogan requested for this guide. It suggests a deliberate, cold and carefully measured identity. It does not imply exact or guaranteed weather outcomes. Keep uncertainty visible wherever forecast information appears.

Set it in IBM Plex Sans 400, sentence case. In a centered lockup, leave at least one quarter of the logo cap height between the visible logo and the slogan. Keep its width comfortably below the wordmark width. In editorial layouts it may be an independent heading in Outfit 600. Omit it from compact app icons and crowded product headers. It is not yet frozen as permanent lettering within the logo.

Supporting descriptor: **Snow forecasts. Grooming reports. Resort guides.** This describes the product; it is not part of the logo.

## Primary identity

**Preserved ID:** 04S-C-A, the Glacial Precision treatment of the 04S-C Snow-built Zero. The original visual reference is the baseline-aligned light wordmark in `assets/logo-approved-reference.png`. Frozen production masters are in `assets/primary/`; use the supplied paths for exports.

### Geometry to preserve

1. A slim, rounded, upright zero with an open counter.
2. Two short ticks facing inward from its left side.
3. A blue drift that forms the bottom outer contour of the zero itself.
4. No navy rim underneath that blue snow.
5. The blue base sits on the lettering baseline; the top aligns optically with the capital S.
6. Clean, geometric xSnow lettering with the selected spacing and weight.

Write the name **0xSnow**, using numeral zero, lowercase x, capital S and lowercase n, o and w. Never replace the zero with a letter O in text.

The wordmark's lettering is custom outlined artwork. **Glacial Precision is a design label and now a candidate slogan, not a font family.** Do not recreate the wordmark by typing 0xSnow in Outfit.

### Forms

- Primary horizontal wordmark: websites, report covers, email mastheads, editorial, signage.
- Standalone zero: compact brand identifiers and app-icon development.
- Inverse: white/ice lettering on navy with the blue base retained. Production light and dark masters share the same geometry; the old inverse raster is historical reference.
- One-color: black and white SVG versions of the primary are included in `assets/primary/`. Proof the silhouette and intended reproduction process at actual size.

### Spacing and minimum size

Let H be the visible cap height. Minimum external clear space X = H / 4 on all sides. Measure from the artwork, including the snow base. Do not count the raster board's padding as part of the logo.

The selected horizontal mark is approximately 5:1 in visible width to cap height. The zero within it is approximately 0.68H wide. These ratios are construction references, not instructions to redraw the approved mark from scratch. Scale the artwork uniformly.

Starting minimums for proofing: horizontal wordmark 160 CSS px or 35 mm wide; standalone symbol 32 CSS px or 8 mm tall. A favicon below 32 px needs a separately proofed optical version. Final print limits depend on process, material and line reproduction.

Do not stretch, tilt, retype, add ticks, reattach a dark lower rim, bury the mark in frost, add an enclosing icy zero, or add shadows to small lettering. Keep high-detail material outside the core small-format logo.

## Selected raised-x alternate: Balanced

**Selected 21 November 2026. Frozen ID: 04S-C-A-alt-A-01.** Balanced is the selected raised-x alternate; it does not replace the standard 04S-C-A primary. Light and dark SVG/PDF files are in `assets/alternate/`. The SVGs are exact copies of the selected study, with no path or spacing changes.

The x stays between the zero and Snow. Use the standard treatment: navy `#071B2E` on light, ice ink `#E7F2FC` on dark, and Snow Blue `#29C3FE` for the gauge base. The blue-x and frosted-lettering experiments were not selected.

Frozen construction in the original master coordinate system:

- Scale the original x uniformly to **48%**; its visible top-left is **(122, 6)**.
- Translate the intact Snow group **-58 units horizontally**, with no vertical translation.
- The gauge stays at its original origin. Its right bound is 108.246; the gap to x is approximately **13.754 units**.
- The scaled x is approximately 54.008 units wide. Its gap to the S bounding edge is approximately **8.398 units**.
- Keep all gauge and Snow paths, selected baseline and round-letter optical overshoot unchanged. Do not retype or redraw them.

Use at least H/4 external clear space. Start proofing at 160 CSS px or 35 mm wide; use the standalone gauge where the complete name becomes too small. Keep the compact app symbol unchanged. Glacial Precision remains a working slogan, separate from the frozen logo.

The standalone `0xSnow-Balanced-Brand-Sheet.pdf` is also page 5 of the full guide. `selection.json` is the machine-readable selection record.

## Color system

Values below are specified sRGB targets. They are not a claim that every generated concept pixel has an exact flat color. Approved reference pixels remain unchanged.

| Brand role | Hex | Use |
|---|---|---|
| Midnight | #071B2E | Brand anchor, dark canvas |
| Snow Blue | #29C3FE | Snowbank and small brand highlights; sampled target near the selected blue |
| Glacier | #8DC4EB | Dark snow strokes and supporting ice accents |
| Ice | #DCEBFA | Light background |
| Frost Paper | #F5F9FC | Quiet, readable surfaces |
| Burgundy | #7B1E2E | Restrained brand moments and occasional primary brand action |

Snow Blue is too light to serve as normal small text on white. Use dark ink for those labels. Avoid making all actions burgundy. Never use burgundy for snowfall quantities, snow probabilities, snow intensity, radar, forecast ranges or model comparisons.

### Appearance tokens

| Role | Frosted Snow / light | Midnight Ice / dark |
|---|---|---|
| Background | #DCEBFA | #071B2E |
| Surface | #F5F9FC | #102A40 |
| Raised surface | #FFFFFF | #102C43 |
| Secondary surface | #EEF4F8 | #18384F |
| Main text | #0C2A4A | #E7F2FC |
| Secondary text | #465C70 | #BDCEDC |
| Divider | #C3D3E0 | #32516A |
| Control border | #7A90A4 | #65859F |
| Routine action | #365C7D | #B8DCF6 |
| Text on solid routine action | #FFFFFF | #071B2E |
| Selected navigation | #DCE8F2 | #24475E |
| Focus | #376F9B | #B8DCF6 |
| Snow stroke | #376F9B | #8DC4EB |
| Expected snow fill | #C5DFF2 | #376B92 |
| Range fill | #E5F1FA | #173B55 |
| Heat-strip maximum | #88B2D5 | #315D7B |
| Brand action | #7B1E2E | #8B2941 |
| Text on brand action | #FFFFFF | #FFFFFF |

The blue focus rule is a proposed refinement for this identity; the reviewed light app currently uses burgundy focus in several places. The CSS in the kit is explicitly scoped and does not overwrite the app.

Keep error, warning and informational states independent of the brand accent. Label their meaning in text and icons. Stale or unavailable data needs an explicit message, not just a different hue.

## Typography

Retain the app's existing licensed fonts:

| Family | Role | Starting style |
|---|---|---|
| Outfit | Titles, section headings, prominent measurements | 600; 28-32 px page title, 22 px section, 34-40 px large metric |
| IBM Plex Sans | Body, controls, labels and explanations | 400-600; 15-16 px body/control, 12-13 px metadata |
| IBM Plex Mono | Dense data, compact timestamps and comparisons | 400; 11-13 px where necessary |

Body leading: 1.45-1.6. Keep tabular comparisons aligned. Prefer ordinary upright text to italics in data. Keep units beside quantities and labels beside navigation icons. Allow browser text resizing; do not make labels unreadably small to retain a rigid layout.

The package includes WOFF2 web fonts, TTF instances used by the PDF and the corresponding OFL licenses. Follow the included font licenses when redistributing. The logo is not included as a font.

## Layout and components

Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 px. Use larger gaps for distinct information groups and smaller gaps for one related measurement.

Radius: 8 px small chips, 12 px controls, 16 px media, 24 px report cards and sheets. Product touch-target standard: at least 44 x 44 CSS px.

Preserve the app's responsive hierarchy: one column with bottom tabs below 900 px; two-column layouts from 900 px; map-led Today with header tabs from 1200 px. Do not place an oversized brand hero above the daily report.

On mobile, show the resort, report time, useful conditions and compact snow outlook before deeper content. Forecast leads with snowfall, retains the original stakes and uses horizontal scrolling if needed instead of compressing them into illegibility.

Routine selected navigation is a flat ice fill. No underline, raised bottom edge or inset bottom shadow. Ordinary inline text links may remain underlined for recognition. Focus is a separate visible ring and must not be clipped by card masks. Hover can shift the surface tone; pressed and disabled states need to remain understandable. Avoid animation in textures. For other transitions, use short, quiet fades and respect reduced-motion preferences.

### Navigation icons

Existing 28 x 28 SVG family: Today sunrise/ridge, Calendar marked day, Forecast fine snowflake with softly fading ruler, Help shield/cross. Most strokes are 1.75 units; Forecast snowflake is 1.25 and ruler ticks 1.1. Render at 26 px mobile and 20 px desktop. Use rounded caps and joins.

Keep the Forecast ruler's softened left edge and rounded ends. Do not add a sharp enclosing stroke or sticker-like cutout behind the snowflake. Preserve visible labels and current-page semantics. An SVG that is decorative inside a labeled link should not duplicate the accessible name. Reused inline Forecast SVGs need unique gradient IDs.

## Frost material

Use the existing `ice-etch-v4.webp` as the material reference. Its small curled etch marks and bubble-like contours evoke solid blue ice. Avoid fern branches, large snowflakes, a concentrated crystalline rim and high-contrast texture behind dense text.

Existing app recipe: repeat the 960 x 960 asset at 480 x 480 CSS px. Light uses a grayscale/inverted presentation at 10% opacity; dark uses the original at 20%. Do not bake those filters into a new source asset or stretch the tile to the card width.

Existing material targets: light card #F6FBFFBD; dark card #112E45C2; light chrome #F3F9FFF0; dark chrome #0B2135F0. These are approximately 74%, 76%, 94% and 94% opaque. Where supported, the existing implementation uses 24 px backdrop blur and 120% saturation. Provide opaque token fallbacks first.

Light the surface gently from the upper left; use a narrow inner highlight and diffuse shadow. Keep the texture behind content and pointer-inert. Do not clip popovers, focus or chart content to the decorative layer. Header and bottom navigation require higher opacity because moving content scrolls beneath them.

For reduced transparency, forced colors and print, remove texture, blur, gradients and decorative shadows. Use opaque surfaces and necessary system-color borders. Full-scale iced art can support a campaign; it is not required on every logo or control. The guide's PDF material examples are visual approximations of a static surface, not browser rendering benchmarks.

## Data visualization

The existing snow-stake charts are part of the product identity. Retain ruler ticks, drift tops, expected fills, low-end marks, hatched upper estimates, model detail and interactions. Retain the daily heat strip and its explicit values.

All weather graphics use the blue/ice ramp. Do not route data through a generic burgundy accent token. In light mode keep heat fills pale enough for dark labels; in dark mode keep them dark enough for light labels. Use outlines, hatching, labels and legends so meaning does not depend on hue alone. Pale decorative fills alone must not carry an essential graphical boundary.

0 means zero. Missing means unavailable, with an explicit label. Separate reported snowfall from predicted snowfall. Show units and time periods, and keep the likely range beside the expected quantity. Use dates in the resort's time zone. Do not count missing days as zero or label a past observation Now.

## Voice

Use calm, direct language with specific sources, dates and units. Be friendly without turning serious conditions into a mascot moment.

- Forecast: “3.7 inches expected over the next 5 days. Likely range 2-6 inches.”
- Grooming: “Map from Fri, Nov 20. Awaiting a newer report.”
- Missing: “Snow report unavailable. Last checked 7:05 AM MT.”
- Timing: “Resort snow: 5:30 AM MT. Forecast valid: 7 AM MT.”

Keep saved-report, observation and forecast-valid times separate. Avoid promises of perfect accuracy, guaranteed powder or implied official resort affiliation. Retain the app's existing affiliation disclaimer wherever it is relevant to resort content.

## Companion marks

- **21A Core Groomer:** selected supporting direction for grooming reports. The concept raster still needs a vector master.
- **48 Resort Fold:** shortlisted family for trail maps and grooming. 48B is shown for its corduroy integration; no final family variant has been frozen.
- **55B Powder Boots / Stake Scout:** selected character direction. Suitable for onboarding, editorial and merchandise; not a substitute for important data or warnings. Later 55B-A through E iterations remain unresolved.
- **Iced chairlift:** earlier primary identity and current implementation reference. Retain as a historical/transition asset. Do not place it beside the new gauge as a competing primary logo by default.

## Supporting graphics and applications

The snowline can divide a campaign, report cover or package with a single continuous curve. Corduroy can create a restrained parallel-line texture on supporting graphics. Neither should obscure type, modify the approved logo or confuse quantitative chart axes.

Website: modest header signature with the resort and report context. Email: opaque, readable masthead rather than dependency on translucent effects. Social: a separate headline and clear brand signature. App tile: compact zero, no slogan. New app-icon exports must be prepared from the final vector and tested under masks.

For maskable icons, keep essential artwork inside the centered circle of radius 40% of the image width; background extends beyond it. Keep regular and maskable exports distinct. Prepare the platform-appropriate dimensions, including the app's current 180/192/512 targets, after final geometry approval. This guide does not ship replacement install icons.

Merchandise: use a restrained chest, label or tag placement and proof real stitches or ink. Packaging: let negative space carry the brand; retain a readable wordmark. Signage: use vectors and proof at viewing distance. Proposed digital and print minimums are starting points, not production guarantees. Convert RGB to print profiles for the actual substrate and proof a spot-color match if needed; no universal CMYK or Pantone match is asserted here.

## Accessibility and validation

Target at least 4.5:1 normal-text contrast and 3:1 for required non-text boundaries. Calculated opaque-token ratios are in `contrast-checks.json`. Those calculations do not cover every translucent/composited state. Test actual rendered backgrounds, focus visibility, text zoom, reduced transparency, forced colors, keyboard operation and realistic mobile targets.

The layout preserves image colors for grooming maps and cameras. Do not invert those assets for dark mode. User-readable units, source status and uncertainty remain part of the design system.

## Status and sources

This guide records the selected 0xSnow identity. At repository import on 21 November 2026, the name had already been changed to 0xSnow, while the app still rendered the chairlift logo. This asset commit does not roll out the gauge wordmark. The app baseline was local commit 95662ad, dated 17 November 2026. Files reviewed: `docs/BRAND.md`, `public/frost.css`, `public/dark.css`, `public/frost-surfaces.css` and `public/index.html`. Earlier Chair 0 guides are historical.

Current masters: 04S-C-A production vectors and selected Balanced A-01 vectors. The unchanged baseline raster is retained for provenance. Asset hashes are in `asset-manifest.json`; the frozen alternate selection is in `selection.json`. Source-image viewports remain presentation coordinates, not vector paths.

External references checked for this guide:

- [W3C: Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [W3C: Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- [web.dev: Maskable icons](https://web.dev/articles/maskable-icon)

Font licensing is documented by the three included OFL files. This guide does not assert trademark clearance or artwork exclusivity.
