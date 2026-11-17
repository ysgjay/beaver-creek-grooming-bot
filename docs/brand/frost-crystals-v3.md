# Crystalline frost · material asset

Created November 17, 2026 after the owner requested a stronger ice/frost feel than the fine grain treatment.

- File: `public/brand/frost-crystals-v3.webp`.
- Source: built-in image-generation tool, new opaque material texture; no input reference image or CLI fallback.
- Source master: 1254 × 1254 PNG. Web export: 960 × 960 WebP, 268,646 bytes; Sharp resize to 960 px, quality 78, effort 6. No retouching or compositing.
- Display scale: fixed 480 × 480 CSS px in both themes and all screen sizes, with repeat tiling. The image was requested as seamless; the restrained surface veil and narrow rim keep repetitions unobtrusive.
- Card surface: same opaque base color with a 94% surface-color veil over the texture. This is a background behind the content, not a tint over charts or images.
- Stronger rim: pointer-transparent pseudo-element, masked to a narrow, fading perimeter. Light opacity 68%, dark 34%. No content clipping or new card stacking context. The card's existing padding keeps data away from the stronger effect.
- Delivery: included in shell v19, shared by every frosted surface. CSS masks are progressive enhancement. Reduced transparency, forced colors, and print remove the texture.

## Final generation prompt

> Use case: photorealistic-natural. Asset type: seamless square material texture tile for a premium ski weather app, not a mockup or interface. Primary request: a very detailed macro photograph of REAL frozen window frost and translucent pale blue ice, filling the entire square edge to edge. The material has dense delicate white microcrystalline needles, tiny interlocking angular ice facets, fern-like microscopic crystal veins, scattered tiny trapped air bubbles and milky hoarfrost patches, with clear glacial blue ice showing in irregular gaps. The scale is MICROSCOPIC: hundreds of small crystals across the image, no individual feature larger than 3 percent of its width. Slight raking cool light brings out crystalline edges and real frozen depth; soft pale blue shaded crevices. An even consistent material throughout, no central subject, no composition, no vignette, no directional gradient, no border. Palette is ice blue, translucent blue-grey, milky white, a few muted steel-blue microcrevices. This should unmistakably look frozen and crystalline, not generic paper grain, metallic noise, fabric, marble, or plain frosted glass. Seamlessly tileable in all directions. Orthographic, perfectly flat surface, no perspective. No giant fern leaves, no separate recognizable branches, no big snowflake symbols, no long cracks, no icicles, no mountains, no objects, no text, no logos, no UI.
