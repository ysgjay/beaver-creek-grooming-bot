# 0xSnow / Agent handoff

## Objective and current status

Use the selected **04S-C-A baseline-aligned** direction to establish the new 0xSnow identity. **Glacial Precision** is a working slogan requested by the owner; it is not yet permanently frozen. The guide and examples are prepared. No website, deployment, repository branch or installed app icon was changed by creating this package.

## Read first

1. `0xSnow-Brand-Guide.pdf` for visual intent.
2. `Brand-Specification.md` for the editable rules.
3. `tokens.json`, `assets/logo-viewports.json` and `asset-manifest.json` for targets, presentation coordinates and source hashes.

## Preserve the approved logo and selected alternate

The primary remains **04S-C-A**. Its frozen SVG/PDF masters are in `assets/primary/`; the unchanged original raster remains in `assets/logo-approved-reference.png` for provenance. Do not retrace the raster, substitute a font or approximate the gauge with a generic pill.

The owner selected **Balanced, 04S-C-A-alt-A-01**, as the raised-x alternate on 21 November 2026. Exact light/dark SVGs from the selected study and matching native-vector PDFs are in `assets/alternate/`. `selection.json` records the choice and exact transforms. The SVG source hashes match the selected study.

For Balanced, use the original x path at 48% scale with visible top-left (122, 6), and translate Snow -58 units horizontally. The gauge and Snow contours and baseline remain unchanged. The x stays between 0 and Snow. Use the standard two-color treatment; other placement and finish studies are not selected.

Both light and dark versions use identical geometry. Preserve the zero's two inward ticks, open counter, blue snow base and lack of a dark lower rim. The original custom lettering is not Outfit or another identified font.

The guide's new page 5 and standalone Balanced brand sheet define this alternate. Earlier primary specimens retain the original raster reference; use the packaged production vectors for export. Companion concepts still need their own production artwork.

## Production and future application

- Core primary and Balanced alternate are native vectors. Do not recreate their paths.
- Proof the intended screen/print size and material. Use 160 px wordmark and 32 px symbol as starting points, not universal production guarantees.
- Existing primary app-icon and motion exports are included in `app-icons/` and `motion/`. This update does not switch the app icon or deploy a new wordmark.
- If adapting an earlier Original Alternate A animation, apply **Balanced A-01** transforms; the older Original A uses different spacing. Snow can cover the gauge edges and partially fill Snow; keep the raised x clear.
- Keep the selected ID and create a new explicit revision for any later visual change. Glacial Precision remains a potential slogan.

## Repository import update

The package was imported on 21 November 2026 after checking main at **b3d9526**. The application name is already 0xSnow; the header and install icon still reference the iced chairlift. The dated PDF audit below remains provenance, not a claim that the rename is outstanding. Read [the Claude branding guide](../CLAUDE_BRANDING.md) before applying assets.

## Existing app baseline

Inspected local repository: `ysgjay/beaver-creek-grooming-bot`, commit **95662ad**, 17 November 2026. This is a dated local snapshot, not a fresh remote or live-site audit.

| Existing file | Concern |
|---|---|
| `public/frost.css` | Main light brand tokens, typography, layout and controls |
| `public/dark.css` | Dark palette and surface-specific appearance |
| `public/frost-surfaces.css` | Etched ice layer, highlight, blur and fallbacks |
| `public/index.html` | Current logos, home link and both navigation icon copies |
| `public/appearance.js` | System/light/dark preference behavior |
| `public/app.css`, `public/app.js` | Existing chart geometry and interactions |
| `public/manifest.webmanifest` | Installed-app metadata and icon references |
| `public/sw.js` | Shell cache and versioned resources |
| `docs/BRAND.md` | Prior Chair 0 identity and product rules |

Check the actual working tree and remote state before future changes. Preserve unrelated modifications. Reconcile the local baseline with current code rather than copying old files wholesale.

## Retained versus proposed

**Retained from the app:** Outfit/Plex fonts, light and dark data palettes, 24 px cards, restrained mobile layout, custom navigation geometry, source/date labels, chart semantics, and the existing `ice-etch-v4` material.

**Proposed in this guide:** 0xSnow name and primary logo, Snow Blue #29C3FE as a brand target near the selected snowbank, Glacial Precision as candidate slogan, blue light-mode focus instead of burgundy, and a clearer separation of primary identity from companions.

**Not selected as final:** the other raised-x spacing studies, ice-blue-x or frosted-lettering treatments, a final 48 variant, or a final 55B child iteration. Earlier iced chairlift assets are included for transition context, not as a competing primary mark.

## Token mapping

The CSS is scoped under `data-oxsnow-appearance` to avoid accidental app changes. Integrate deliberately; do not paste it over existing styles or create a second conflicting theme controller.

| Guide token | Existing role |
|---|---|
| `--ox-background` | `--bg` |
| `--ox-surface` | `--frost-paper` |
| `--ox-text` | `--ink` |
| `--ox-text-secondary` | `--ice-secondary` / appropriate `--ink-2` context |
| `--ox-snow-stroke` | `--snow` |
| `--ox-snow-fill` | `--snow-fill` |
| `--ox-snow-range` | `--frost-metric-soft` |
| `--ox-snow-heat-max` | `--frost-metric-heat` |
| `--ox-selected` | `--frost-selected` |
| `--ox-control-border` | `--frost-control` |

Do not map `--ox-brand-action` into charts. Keep blue/ice strokes, expected fills, uncertainty hatching, drift tops, ruler ticks, low markers, labels, model details and current interactions. Missing data must never become zero. Keep source times and units intact.

## Material implementation

Use the existing texture file and fixed 480 CSS px tile scale. Preserve proper stacking, pointer-inert decoration, opaque fallbacks, high-opacity chrome and unclipped interactive overflow. Keep the texture behind chart labels and images. Respect reduced motion, reduced transparency, forced colors and print.

The PDF material previews are static illustrative approximations. The existing browser code remains the source for exact current behavior. Avoid adding giant crystals or a visible fern-like rim to chase stronger frost.

## Icon and font assets

`assets/navigation/*.svg` are genuine vectors extracted from the existing app. Keep their 28-unit geometry, visible link labels and decorative SVG semantics. Inline Forecast copies require unique gradient IDs. Their `.nav-ice` shapes are controlled by surrounding selection CSS.

The included Outfit, IBM Plex Sans and IBM Plex Mono files have their OFL licenses alongside them. The wordmark is not one of these fonts. Do not attempt to identify it as a named font without actual evidence.

## Future rollout sequence

1. Use the frozen primary or selected Balanced alternate assets; confirm the intended placement from the implementation request.
2. Derive needed application exports and test real minimum sizes and icon masks.
3. Update header/home link, email masthead, metadata, manifest, home-screen icons, social cards and documentation as one coherent identity rollout.
4. Preserve app state, appearance behavior and data flows. Version new assets and update the service-worker shell cache as appropriate.
5. Review desktop and mobile Today/Forecast/Calendar/Help in both appearances, including reduced-transparency and forced-color states, keyboard focus, zoom, chart interactions and fresh/stale/missing data.

Creating this guide did not authorize sending messages, publishing a marketing claim or merging a new implementation. Follow any later explicit implementation request and the active repository instructions.
