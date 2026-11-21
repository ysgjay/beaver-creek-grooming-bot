# 0xSnow brand kit / 1.1

Prepared 21 November 2026 around **04S-C-A**, the selected snow-stake zero with Glacial Precision lettering and the aligned baseline.

**Working slogan: Glacial Precision.** It is a candidate, not a permanently locked tagline.

Start with **0xSnow-Brand-Guide.pdf**, a 26-page visual guide. The PDF has a clickable outline and source links.

**New in 1.1:** Balanced (04S-C-A-alt-A-01) is the selected raised-x alternate. Page 5 and the standalone **0xSnow-Balanced-Brand-Sheet.pdf** show the exact light/dark design, spacing, colors and usage. The primary remains unchanged.

## Included

- **assets/alternate/**: exact selected Balanced light/dark SVGs and native-vector PDFs.
- **assets/primary/**: existing primary and gauge SVG/PDF masters, plus primary one-color SVGs.
- **selection.json**: frozen alternate selection, proportions and treatment.
- **Brand-Specification.md**: editable brand standards, color, type, layout, material, data and application rules.
- **Agent-Handoff.md**: implementation decisions, preserved details, exact references and asset status and future application work.
- **tokens.json / tokens.css**: scoped, reusable color and layout targets for light and dark appearances. These are not a drop-in replacement for existing app styles.
- **contrast-checks.json**: calculated opaque-color contrast ratios.
- **assets/logo-approved-reference.png**: the unchanged approved raster concept board.
- **assets/logo-viewports.json**: non-destructive viewing rectangles for the primary wordmark, standalone zero and inverse study.
- **assets/companions/**: preserved reference boards for 21A Core Groomer, 48 Resort Fold and 55B Powder Boots.
- **assets/navigation/**: existing app navigation SVGs, extracted without changing their geometry.
- **assets/material/**: the app's etched ice texture and its provenance record.
- **assets/fonts/**: existing Outfit, IBM Plex Sans and IBM Plex Mono files, with the bundled OFL licenses. TTF instances support PDF generation; WOFF2 files support the website.
- **assets/heritage/**: earlier chairlift assets, kept explicitly as transition references.
- **asset-manifest.json**: source paths within this package, byte counts and SHA-256 hashes.
- **source/**: editable PDF layout source, selected-asset exporter and frozen geometry.

## What is settled

The selected primary visual direction is 04S-C-A. Preserve the zero's two inward left ticks, open center, blue snow base, proportions and aligned baseline. The name is **0xSnow**. The selected wordmark is custom outlined lettering; it is not Outfit or another identified font.

## Production status

Core primary and Balanced alternate logo assets are supplied as native vectors. The Balanced SVGs are unchanged copies of the selected A-01 study; the light/dark PDFs use the same frozen geometry. The original raster references and companion concept boards remain clearly identified as references.

The primary page examples preserve their original reference images. Use `assets/primary/` and `assets/alternate/` for actual vector exports. Application-specific print separations, embroidery and physical reproduction still require process-specific proofing. The `app-icons/` directory contains the existing gauge app-icon exports for a future rollout; current app references still use the chairlift. `motion/` contains the latest primary-wordmark snow accumulation SVGs.

The app examples and numerical values are illustrative. This package does not modify the website, deploy changes or replace existing home-screen icons. The PDF preserves its design audit baseline at commit **95662ad** (17 November 2026). The current repository was rechecked at **b3d9526** when importing this package: the name is already 0xSnow, and the rendered app logo remains the chairlift. See [Claude branding guide](../CLAUDE_BRANDING.md) for the current implementation distinction.

## Rebuild

With Python, ReportLab, Pillow and pypdf installed, run `python source/build_brand_guide.py` from any directory. The script finds the packaged fonts and artwork relative to itself. `source/export_balanced.py` regenerates the selected alternate PDF assets. The guide build also exports page 5 as the standalone Balanced sheet. The original workspace-only preparation script is intentionally omitted; this repository copy rebuilds from its packaged assets.

Use the current guide for the proposed 0xSnow identity; keep earlier Chair 0 guides as historical product references.
