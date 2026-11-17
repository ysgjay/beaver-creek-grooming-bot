# Frost grain · surface finish

Revision date: November 17, 2026. Replaces the repeated fern artwork after review of the production desktop screen.

- File: `public/brand/frost-grain-v2.svg`, a hand-authored 256 × 256 SVG noise tile.
- Construction: deterministic, stitched `feTurbulence` with three octaves, frequency `.78`, and seed `17`. A color matrix gives the grain a pale ice hue and low alpha. No generated bitmap or external source is used.
- Scale: fixed 180 × 180 CSS pixels in every container. It never grows into a recognizable pattern on larger cards.
- Finish: grain beneath a surface-color gradient, with separate soft corner light and a restrained rim. Grain is completely covered after 20 px on cards, 22 px in the header, and 18 px in the bottom nav. Titles and data remain on the original opaque surfaces.
- Accessibility: decorative background only; no interactive layer, motion, new clipping, or stacking context. Reduced transparency, forced colors, and print remove it. In forced colors the card and chrome borders use `CanvasText`.
- Delivery: shared by all surfaces, pre-cached in shell v18; the old 96 KB branch image is no longer requested. Preserve a versioned filename when changing the texture.
