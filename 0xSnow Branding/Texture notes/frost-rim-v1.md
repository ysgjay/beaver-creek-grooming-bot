# Frost rim · retired asset record

Retired from the interface on November 17, 2026 after desktop review: the pattern became too large and repetitive when scaled across cards. Retained only as an asset history reference; no longer loaded or cached by the app. Current finish: `frost-crystals-v3.md`.

Original direction: the November 17, 2026 light/dark frost mockups for the header, bottom navigation, and card edges. This is decorative surface art, not an information-bearing image or a replacement logo.

- File: `public/brand/frost-rim-v1.webp`
- Created: November 17, 2026 with the built-in image-generation tool (transparent background), using the approved dark comparison board as a visual reference.
- Source master: 2172 × 724 transparent PNG; export: 1200 × 400 RGBA WebP, 96,360 bytes.
- Export: Sharp resize to width 1200, WebP quality 78, alpha quality 90, effort 6. No retouching or compositing.
- Application: CSS background only, preserving the image aspect ratio and fading through an opaque surface-color gradient. Dark and light veils are set in `public/frost-surfaces.css`.
- Delivery: versioned filename, shared by all three surfaces, included in the service-worker shell. Change the filename and cache version when replacing the artwork.

## Generation prompt

> Create ONLY a reusable decorative frost texture asset inspired by the fine crystalline fern frost at the TOP EDGES of the AFTER cards in the attached approved design. Do not draw UI or text or a card. Output a wide horizontal 3:1 TRANSPARENT PNG: delicate isolated white and very pale ice blue fern-shaped ice crystal LINEWORK, growing down from top left and top right corners, and a few smaller crystal sprigs along the top edge. Fine branches are individually separated by large transparent spaces, like etched botanical feathers, with tiny pointed crystal veins. NOT snow accumulations, NOT snow drifts, NOT opaque frost slabs, NOT a filled jagged silhouette, NOT hanging icicles. Crucially the gaps BETWEEN individual ice-fern branches are completely transparent. This is a line-and-speckle overlay, no solid body or strip. Coverage is sparse: 75–85 percent of the whole canvas empty transparent. Top left and right clusters extend down only the first 40 percent of the canvas, middle cluster extends only 15 percent. Lower half entirely transparent. No background hue, no navy, no gradient background, no shadows, no panel, no border, no logo, no text. Delicate microscopic sparkling edge grains and thin fern branches with a little translucency. Crisp detail designed to remain recognizable when shown as a 400px-wide horizontal edge on a dark navy card.
