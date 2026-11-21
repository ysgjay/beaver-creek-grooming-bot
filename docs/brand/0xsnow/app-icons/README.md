# Gauge app-icon exports / prepared, not deployed

These files are the previously prepared 04S-C-A gauge app-icon assets from the
production-vector kit. The running app still references the dark iced chairlift.
This documentation commit does not switch Apple touch icons, manifest icons,
favicons or service-worker assets.

The SVG/PDF files are native vectors. PNG exports cover 1024, 512, 192 and 180 px
as named; small favicon PNGs and an ICO are also included. Full-bleed backgrounds
and the centered symbol preserve the original mask-safe composition. Both
regular and explicitly named maskable exports are retained.

`manifest-snippet.json` is a reference snippet for a future integration. Check
and adapt its paths to the actual runtime directory rather than pasting it
blindly. The current manifest and platform references are in `public/`.

The compact symbol has no x or slogan. Selecting Balanced as the raised-x
wordmark alternate did not change this icon geometry.
