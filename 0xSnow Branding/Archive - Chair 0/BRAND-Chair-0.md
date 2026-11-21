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

Outfit is for headings and prominent measurements, IBM Plex Sans for interface text, and IBM Plex Mono for data. The licensed WOFF2 files are self-hosted in `public/brand/fonts/`; each family includes its OFL license. Cards use softly lit, translucent blue-ice surfaces over a pale ice background. Fine curled etching runs across the header, bottom navigation, and cards at a constant scale. Smooth highlights suggest rounded glass thickness; there is no deposited frost or masked perimeter. The reference is the dark iced app icon, with its clear blue material and tiny etched details.

## Logo files

- `public/brand/app-icon-dark-{180,192,512}.png`: dark navy iced app tile for home-screen installation. The 180 px PNG is the Apple touch icon; the manifest uses 192 and 512 px PNGs, with maskable support at 512 px. The opaque artwork keeps the terminal, ring, and chairs within the central mask-safe circle. The 1024 px master is stored alongside these exports. Use versioned filenames for future icon replacements.
- `public/icon.svg` and `icon-{180,192,512}.png`: flat burgundy utility icon with an ice background, retained for the small favicon and notifications. It is no longer advertised as an install icon.
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

## Reading the report

Today separates the saved report time from resort snow and forecast valid times. Base depth, mph, and gust labels are explicit. Grooming shows the printed map date and its age; an unknown date stays unknown. List-based feeds label when they were checked. A compact blue snow outlook appears above grooming on phones.

On phones, Forecast starts with snowfall. Keep the original stake geometry and give each day roughly 50 px of width, using horizontal scrolling and labeled 44 px arrow buttons. All ten days fit on desktop. A selected day leads with the expected snowfall and likely range; model votes expand underneath. Modal sheets and full-size maps use native dialogs with Escape, contained keyboard focus, and focus restoration.

Source labels and summaries must use real report dates and numbers. Past hours must not be labeled Now, missing days must not count as zero, and five-day summaries require five dated daily values. Forecast source dates remain visible when the report is older.

## Reusing the style

For a new page, email header, or sibling product, start from these defaults:

1. **Background:** ice `#DCEBFA` with a soft white radial glow at top left; content sits on translucent blue-ice cards with a soft 1 px edge, 24 px radius, and diffuse navy shadow. Use the shared material tokens in `frost-surfaces.css`; `#F5F9FC` remains the opaque fallback.
2. **Type:** Outfit 600 for headings and big numbers, IBM Plex Sans for interface text, IBM Plex Mono for data and small kickers (11 px, 0.05em tracking). Self-host the WOFF2 files with their OFL licenses.
3. **Text color:** ink `#0C2A4A`, secondary `#52677B`. Quiet actions and links use `#365C7D`; ordinary links stay underlined.
4. **Controls:** 44 px minimum touch targets, 12 px radius on buttons and inputs, `#7A90A4` control borders, flat `#DCE8F2` fill for a selected tab, solid `#365C7D` for a pressed segment.
5. **Data:** every snow and weather graphic uses the blue/ice ramp (`#376F9B`, `#C5DFF2`, `#E5F1FA`, `#88B2D5`), never burgundy.
6. **Burgundy `#7B1E2E`:** the logo plus the accent for primary actions, focus, pills, and links (see below). Never in data graphics.
7. **Two appearances.** Frosted Snow is light; Midnight Ice is dark. Follow the device by default, with System, Light, and Dark choices under Help → Appearance. Keep the same layout and blue/ice data language in both.
8. Write the brand as "Chair 0" with the numeral, and keep "Not affiliated with Vail Resorts" wherever the brand appears with resort content.

## Burgundy in the interface

Decided 11/16: burgundy `#7B1E2E` is the app's accent, replacing the earlier logo-only rule. Besides the logo and icons it appears on primary buttons (email sign-up submit), the patrol card border, keyboard focus outlines, status pills, featured run chips, the Help kicker, plain `<a>` links, and the resort menu's current resort and favorite star. Snow and weather graphics stay blue/ice, and selected tabs, segments, and quiet links stay ink or muted blue.

## Navigation icons

The custom alpine family lives inline in `public/index.html`, shared visually by mobile bottom tabs and desktop header tabs:

- **Today:** sunrise over a snow-capped ridge.
- **Calendar:** bound calendar with a single marked day.
- **Forecast:** a fine-lined snowflake in front of a pale ice ruler. The ruler has rounded ends and a transparent-to-ice fill that softens its left edge. It has no outer stroke or cutout around the snowflake; only the measuring ticks are drawn. Each navigation copy has its own gradient ID.
- **Help:** patrol shield with a cross.

Use a 28 × 28 viewBox and rounded caps and joins. Most strokes are 1.75 units; the Forecast snowflake uses 1.25 units and its ruler ticks 1.1 units at 65% opacity. Render at 26 px on mobile and 20 px in the desktop header. Idle icons are slate outlines; the selected icon uses ink with ice `#C5DFF2` in its `nav-ice` shapes. The Forecast ruler retains its subtle ice fill in either state. The surrounding selected tab stays flat, without an underline or raised bottom edge. Avoid texture, shadows, or burgundy in these small navigation symbols.

Keep the visible labels, the link's `aria-current="page"`, and the existing generous touch targets. The SVGs are decorative (`aria-hidden="true"`, `focusable="false"`); the link supplies the name and keyboard focus. Both navigation copies must use the same geometry. No image downloads or additional JavaScript are needed.

## Midnight Ice

The dark appearance is derived from the navy glass-and-ice logo artwork. Use `#071B2E` for the background, `#102A40` for report cards, `#18384F` for secondary surfaces, `#E7F2FC` for primary text, and `#A9BFD2` for secondary text. Actions and focus use ice blue `#B8DCF6`; selected tabs use `#24475E`. Snow strokes use `#8DC4EB`, expected fills `#376B92`, and uncertainty fills `#173B55`. Heat-strip and calendar fills stay dark enough for light labels. Burgundy `#8B2941` is reserved for primary actions and small brand accents, with white button text.

Use translucent navy-blue glass with fine etched detail across each pane and soft optical highlights. Cards have a 76% tinted fill; header and bottom navigation use a 94% fill for legibility over scrolling content. Secondary text on glass uses `#BDCEDC` in dark mode (`#465C70` in light mode). Opaque sheets and menus remain distinct. Do not invert grooming maps or cameras. Native controls, sheets, tooltips, menus, model tables, and radar must all respect the resolved appearance. Primary and secondary text exceed 4.5:1 contrast on their corresponding surfaces. `appearance.js` runs before styles to avoid a light flash; it respects saved choices, live device changes, and blocked storage. Preferences use `chair0.appearance` and sync between open tabs. `dark.css` supplies the dark palette; `frost-surfaces.css` loads after it.

Home-screen icon setup follows [Apple touch-icon guidance](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html) and the [maskable icon safe zone](https://web.dev/articles/maskable-icon). The launch artwork stays navy in either appearance. Existing installed shortcuts may retain cached artwork; removing and adding the shortcut again is the fallback.

## Implementation

`public/frost.css` loads after `themes.css` and `app.css`, scoped to `html[data-brand="frosted-snow"]`. `dark.css` follows, then `public/frost-surfaces.css` adds the shared material treatment on both the main app and Snow Audit. The base files retain chart geometry and responsive page structure. `public/sw.js` caches the stylesheets, utility icons, fonts, material mark, and frost texture with the app shell. Update its shell version when those resources change. Reduced motion, reduced transparency, keyboard focus, and forced colors have explicit treatments.

### Ice-glass surfaces · November 17, 2026

- Current material: `public/brand/ice-etch-v4.webp`, derived from the owner's dark navy iced app-icon reference. Tiny curled etch marks and trapped-bubble contours cover the whole surface. The prior fern, grain-only, and crystalline-rim treatments are retired.
- The 960 × 960 export repeats at a fixed 480 × 480 CSS px. Light mode inverts a grayscale rendering at 10% opacity; dark mode uses the original navy texture at 20%. Never stretch it to a card's width or use a concentrated perimeter mask.
- Surface lighting combines a diffuse upper-left glow, a quiet diagonal reflection, a smooth inner highlight, and a soft shadow. Cards use 74% pale glass in light mode and 76% navy glass in dark mode. Header and mobile nav use 94% tinted glass in both modes, with stronger secondary-text colors to protect readability over moving content.
- Supported browsers blur the backdrop by 24 px with 120% saturation. Without backdrop-filter support, the base remains opaque. No animated texture or JavaScript is added. Sheets, menus, images, and data fills retain their existing surfaces; the texture is behind content, never laid over it.
- Each card establishes its own stacking context to hold the decorative pseudo-element behind its content. An open `.votes-pop` lifts its card above sibling cards. Do not clip overflow: desktop forecast popovers, focus rings, and charts must remain usable. Mobile forecast details keep their native dialog.
- Selected tabs stay flat with no underline, raised lip, or bottom shadow. Custom icons, touch targets, the patrol card's burgundy border, and the original snowfall stakes/blue data palette are unchanged.
- Reduced transparency, forced colors, and print remove texture, blur, gradients, and decorative shadows, restoring opaque panels. Forced colors retains a system-color border.
- The 119,830-byte texture is shared by the app and Snow Audit and pre-cached with shell v20. Asset provenance, final prompt, and validation notes: `docs/brand/ice-etch-v4.md`.

The backend, forecast calculations, delivery schedule, opt-in behavior, and resort data are unchanged by this styling update.
