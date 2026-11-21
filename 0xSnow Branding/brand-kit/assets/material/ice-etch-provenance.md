# Etched ice glass · material asset

Created November 17, 2026 to match the owner's dark navy iced app-icon reference. The material is continuous translucent blue ice with fine curled etching, soft rounded highlights, and optical depth. The previous deposited-frost perimeter is retired.

- File: `public/brand/ice-etch-v4.webp`.
- Source: built-in image generation, with the owner-supplied `codex-clipboard-bb7b7dc9-fe70-4bc0-8ae2-6848b7ba9f99.png` as the sole material reference. No CLI fallback.
- Source master: `exec-11c20fc5-b4b9-4bdb-87cc-79c72f9111f1.png`, 1254 × 1254 opaque PNG. Original remains in the local generated-images directory.
- Web export: 960 × 960 WebP, 119,830 bytes; Sharp resize to 960 px, quality 82, effort 6. No bitmap retouching or compositing.
- Display: repeat at 480 × 480 CSS px, constant across desktop and phone layouts. Dark uses the navy tile at 20% opacity. Light uses CSS grayscale/invert at 10%. The entire surface is textured; there is no rim mask, edge fade, stretching, or animation.
- Lighting and depth come from CSS gradients, inner highlights, soft shadows, and 24 px backdrop blur with 120% saturation. Cards use 74% light / 76% dark tinted fill. Chrome uses 94% fill to protect legibility. Texture is behind all children; maps, cameras, and snow fills are not tinted by the texture.
- A card stacking context contains the negative-z decorative layer. `.card:has(.votes-pop)` raises an open forecast popover above sibling cards. Content remains unclipped. Mobile details remain native dialogs.
- Unsupported backdrop filtering retains an opaque base. Reduced transparency, forced colors, and print remove texture, lighting, blur, and shadows. Forced colors keeps a system-color border.
- Delivery: one shared texture, pre-cached with shell v20. Earlier textures remain historical assets but are no longer pre-cached or referenced by current surfaces.

## Validation

- Visually checked in light and dark Chrome at 1587 × 944 and 390 × 844, including header and bottom navigation over scrolled map/camera content. No visible tile boundary at the intended display scale.
- Desktop forecast popover remains above adjacent cards; mobile day sheet opens and closes. At 320 px, page width stays 320 px and bottom-nav links retain 52 px heights.
- Surface secondary text is `#465C70` in light mode and `#BDCEDC` in dark mode. Conservative composition of the texture's brightest/darkest pixels with the chrome over black/white gives at least 4.6:1 for these secondary labels; primary text has more contrast. The calculation bounds both gradient layers at their maximum simultaneously in dark mode. Actual texture contrasts are usually much lower. This is a targeted surface check, not a whole-site accessibility certification.
- Original snow stakes, uncertainty hatching, ruler ticks, blue/ice data colors, flat selected tabs, and brand accents remain intact.
- Existing checks passed locally: 107 Python tests (2 skipped), 17 Node tests, all six JavaScript syntax checks, all 25 shell assets present, and clean diff formatting. GitHub CI repeats the complete suites for the PR.

## Final generation prompt

> Generate a production MATERIAL TEXTURE TILE, square, perfectly seamless and continuous when repeated horizontally and vertically. Use the uploaded image ONLY as a close material reference: match the very fine etched curved ice lines on its DARK NAVY glass tile, away from the logo and border. This output is just a flat square crop of that material filling EVERY pixel, with NO outer edge or vignette. Uniform deep midnight navy #08283f base with delicate icy silver-blue etched hairlines: tiny irregular curling contours, short wavy ice striations, minute trapped bubble rings, densely but irregularly distributed across the entire tile, including all four edges. Clear translucent blue ice, smooth beneath the etched details, clean precision surface. The pattern is a microscopic filigree of curved lines, NOT cloud patches, NOT scratches all going the same direction, NOT snowflake shapes, NOT crystalline rubble, NOT fern branches, NOT speckled sandpaper. Make the fine etched lines legible against the navy while keeping a refined low-contrast material appearance. No individual mark or group larger than 2 percent of canvas width; hundreds of small etched curls across the square. Completely even coverage, illumination, density, color, and opacity from center to every edge. No directional light or gradient, no corner shadows, NO EDGE FADING, NO ROUNDING. Fully opaque edge-to-edge, no transparency. No chairlift, no emblem, no red, no text, no border, no bevel, no surrounding background. Orthographic texture scan, not an object or mockup.
