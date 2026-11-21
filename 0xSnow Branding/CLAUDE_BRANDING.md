# 0xSnow branding guide for Claude

Updated 21 November 2026. Repository implementation checked at `b3d9526` before
this asset commit. This is a design decision record and implementation handoff,
not a request to redesign or deploy the interface.

## Start here

1. [Selection record](brand-kit/selection.json): exact IDs, status and geometry.
2. [Balanced brand sheet](brand-kit/0xSnow-Balanced-Brand-Sheet.pdf): selected raised-x
   alternate in light and dark, also page 5 of the full guide.
3. [Full brand guide v1.1](brand-kit/0xSnow-Brand-Guide.pdf) and
   [editable specification](brand-kit/Brand-Specification.md): identity, colors,
   type, material, product and applications.
4. [Agent handoff](brand-kit/Agent-Handoff.md): preservation and application details.
5. [Current product rules](../docs/BRAND.md): existing CSS, icons and interactions.

Use the selection record for the frozen artwork and the current repository
files for implementation state. The PDF's original code audit was from
17 November; it is not evidence of what is deployed today. The owner's newer
instructions take precedence over this record.

## What is selected, and what is implemented

| Item | Status | Source |
|---|---|---|
| Name | 0xSnow; already used in the app, manifest and public metadata | `public/index.html`, `public/manifest.webmanifest` |
| Standard primary wordmark | 04S-C-A; baseline-aligned snow-gauge zero and full-size xSnow | [Primary vectors](brand-kit/assets/primary/) |
| Raised-x alternate | **Balanced / 04S-C-A-alt-A-01**, explicitly selected by the owner | [Balanced vectors](brand-kit/assets/alternate/) |
| Slogan | **Glacial Precision** is potential/working, not frozen into the logo | Specification and selection record |
| Current app artwork | Iced chairlift header and dark chairlift home-screen icon remain referenced | `public/brand/frosted-logo.webp`, `public/brand/app-icon-dark-*.png` |
| Gauge app-icon exports | Prepared assets for a future identity rollout; not installed by this commit | [Gauge icons](brand-kit/app-icons/) |
| Snow accumulation | Current motion samples for the standard primary and standalone gauge | [Motion assets and notes](brand-kit/motion/README.md) |
| Other raised-x studies / finish experiments | Not selected | Keep them out of the default logo system |

The user chose Balanced as the **alternate**, not as a replacement for the
standard primary. Use the exact standard two-color Balanced design. Neither the
ice-blue x nor the frosted-lettering experiment was approved as its default.

## How the identity evolved

- The earlier Chair 0 / Snow Desk identity used a head-on chairlift terminal,
  an open bullwheel ring, a center post and two chairs. Burgundy was confined
  increasingly to brand accents; snow metrics stayed blue/ice.
- The product adopted light and dark appearances, custom alpine navigation,
  clearer source/time labels and compact snow-first mobile presentation.
- The preferred material became blue ice with fine etching and small trapped
  bubbles across the pane. Fern-like crystals and a defined frost perimeter
  were rejected in favor of subtle depth and texture.
- Broad 0xSnow logo exploration converged on **04S-C-A**: a slender measuring
  zero, two inward left ticks and a blue snowbank forming the bottom contour.
  The zero's bottom was aligned with the lettering, retaining optical overshoot.
- Native vectors, matching light/dark assets and app-icon exports were prepared.
  The lettering is custom artwork, not a named font.
- Motion was revised from a wave to settling snow: the fill covers the entire
  pill, including its sides and ticks; the x remains clear. A second version
  partially fills the lower part of Snow.
- The owner specified that a raised x belongs **between 0 and Snow**, then
  selected **Balanced A-01** from the detailed Alternate A studies.

Supporting concepts remain separate: 21A Core Groomer for grooming reports,
the Resort Fold family for maps/grooming, and 55B Stake Scout as a possible
character. Their included images are concept references, not finished vectors
or interchangeable primary logos. See `brand-kit/assets/companions/`.

## Frozen geometry: do not reconstruct it

Use these files directly:

- [Balanced light SVG](brand-kit/assets/alternate/04S-C-A-alt-A-01-light.svg)
- [Balanced dark SVG](brand-kit/assets/alternate/04S-C-A-alt-A-01-dark.svg)
- Matching native-vector PDFs in the same directory.
- [Primary light SVG](brand-kit/assets/primary/0xsnow-wordmark-light.svg) and
  [primary dark SVG](brand-kit/assets/primary/0xsnow-wordmark-dark.svg).
- `brand-kit/source/geometry.json` is the frozen path source; `selection.json`
  records the selected alternate transforms.

Balanced keeps the original gauge at its origin, scales the original x uniformly
to **0.48**, places the x's visible top-left at **(122, 6)** in master coordinates,
and translates the intact Snow group **(-58, 0)**. The gauge-to-x clearance is
approximately **13.754 units**, and x-to-S bounding-box clearance is approximately
**8.398 units**. These numbers document the supplied files; do not use them to
approximate a new mark.

Preserve the two left ticks, open counter, selected width and snow contour. The
blue snow forms the bottom outside silhouette: there is **no dark rim beneath
it**. Keep the gauge and Snow baseline unchanged, including round-letter optical
overshoot. Do not stretch the zero to make mathematical bounding boxes line up.
Both appearances share identical paths. Do not independently redraw the inverse.

Maintain at least one quarter of the cap height as exterior clear space. Start
proofing full wordmarks at 160 CSS px / 35 mm wide, and the standalone symbol at
32 px / 8 mm tall. Use the gauge at tiny sizes rather than making the raised x
unreadable. The supplied SVG's viewBox padding is not itself the required clear
space. Scale uniformly and measure from the visible mark.

SVGs and the selected asset PDFs are native vectors. PNG boards and companion
references are raster previews. The standard primary examples in the full PDF
retain the original reference images; actual exports should use the vector files.

## Color and type

| Role | Value |
|---|---|
| Midnight brand anchor | `#071B2E` |
| Light logo ink on dark | `#E7F2FC` |
| Logo snowbank | `#29C3FE` |
| Glacier | `#8DC4EB` |
| Ice background | `#DCEBFA` |
| Frost Paper | `#F5F9FC` |
| Restrained burgundy accent | `#7B1E2E` |

Snowfall, accumulation, probability, forecast ranges, model votes, weather heat
cells and radar use **blue/ice**, never burgundy. Brand Snow Blue is separate
from chart tokens. Preserve the existing chart fills/strokes and uncertainty
semantics; do not globally replace data colors with a brand accent.

Use Outfit for headings/large numbers, IBM Plex Sans for interface/body, and
IBM Plex Mono for dense data/timestamps. The licensed fonts already live in
`public/brand/fonts/`; the guide includes licensed copies for offline rebuilding.
The logo is **custom outlined lettering**. Do not retype it in Outfit or identify
Glacial Precision as a font. The working slogan is separate, normally Plex Sans
400 in sentence case; omit it in compact headers and icons.

## Frost, usability and current app details

- Keep the fine etched ice material across the header, bottom navigation and
  card shell; avoid giant crystals, branch patterns or a sharp frosted border.
- The current material is `public/brand/ice-etch-v4.webp`, tiled at a fixed
  480 CSS px. Read `public/frost-surfaces.css` for actual composited values and
  fallbacks. Keep texture behind labels, maps, images and charts.
- Preserve the original forecast stakes and Today heat strip: ruler ticks,
  snow drift tops, expected fill, low-end markers, uncertainty hatching, model
  detail and interactions all carry meaning.
- Selected navigation uses a flat ice fill with **no underline, raised bottom
  edge or inset bottom shadow**. Keyboard focus remains separate and visible.
- Custom nav icons: sunrise/ridge, calendar, fine snowflake with a softly fading
  rounded ruler, and patrol shield. The Forecast ruler must not gain a hard
  left edge or a sticker-like cutout around the snowflake. Both nav copies need
  matching geometry and unique gradient IDs.
- Keep resort/source dates, units, time periods and uncertainty next to the
  data. Missing is not zero; historical observations must not read as Now.
- Preserve System/Light/Dark behavior and the `chair0.appearance` storage key so
  existing users keep their preference. A new brand name alone is not a reason
  to rename technical resources or saved-state keys.
- Maintain reduced motion/transparency, forced-color and print fallbacks; keep
  touch targets, keyboard focus, native dialog behavior and popovers usable.

## Motion direction

See [motion/README.md](brand-kit/motion/README.md) for the supplied SVG families.
The current samples accumulate for eight seconds in a ten-second loop, with a
brief hold and opacity reset instead of snow draining downward. One-shot files
freeze at the completed state.

Snow deposits grow monotonically upward, with a shallow uneven surface,
stationary fine grain and small falling particles. The fill covers the gauge's
sidewalls and ticks, leaving a faint rim. An optional version partially fills
S, n, o and w while preserving their counters; x stays clear. Static/reduced-motion
fallbacks preserve the selected original static logo.

These shipped motion files use the **standard primary's full-size x**, not
Balanced. If the user requests Balanced motion, preserve A-01's transforms
exactly for the visible paths, matching letter clips and static fallback. Do
not reuse the older Original Alternate A spacing (x at 126,7; Snow shift -52).
Do not animate the raised x, use a traveling liquid wave, or present decorative
logo fill as a measured amount of snowfall.

## Applying the brand in a future implementation task

This commit stores documentation and assets under `docs/`; it does not change
runtime imports. The current header points to `/brand/frosted-logo.webp`; the
Apple touch icon, manifest and organization metadata still use chairlift files.
The selected wordmark is ready for an explicitly scoped rollout.

When asked to apply it:

1. Read the current relevant code and the requested placement. Choose primary,
   Balanced alternate or compact gauge for that role; keep the resort and report
   content prominent. Do not infer a new homepage layout from a brand mockup.
2. Copy the selected master into an appropriate versioned runtime asset path.
   Preserve geometry, accessible link names and appropriate dimensions. Avoid
   placing a large wordmark inside an app-icon mask.
3. Update the intended references together: header/Help, emails, favicon,
   install icons, social metadata, manifest and service-worker cache only as
   required by the requested rollout. Existing installed icons may be cached.
4. Test desktop/mobile and both appearances; inspect legibility at real size,
   focus/zoom/reduced-motion fallbacks and chart interactions. Keep data fetching,
   forecast math, time windows, subscriptions and report delivery unchanged by a
   branding-only change.
5. Keep the guide, selection record, manifest hashes and handoff synchronized.
   New geometry or an explicitly requested new finish should get a new revision
   instead of silently changing a frozen ID.

For branding assets/docs, validate referenced files, exact master hashes,
SVG/PDF integrity and link paths. For runtime changes, use the repository's CI
checks in `.github/workflows/ci.yml` and the relevant visual/interaction checks.
Do not run report-sending commands as a branding test.

## Rebuild and provenance

The guide package is self-contained. From `0xSnow Branding/brand-kit/`, with ReportLab,
Pillow and pypdf available:

```sh
python source/export_balanced.py
python source/build_brand_guide.py
```

This regenerates the exact Balanced PDFs, the 26-page guide and the standalone
page-5 sheet. The existing SVG masters are not retraced or overwritten. Render
changed PDF pages before delivery. See `verification.json` and
`asset-manifest.json` for the recorded checks and hashes.
