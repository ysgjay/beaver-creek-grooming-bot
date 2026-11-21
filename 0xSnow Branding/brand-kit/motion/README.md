# Snow accumulation v2 / standard primary

These are the latest approved-direction motion samples from the logo session,
using the standard 04S-C-A wordmark or standalone gauge. They are not connected
to the running app. Balanced A-01 remains a separately selected static alternate.

Each family has light/dark and loop/once SVG files:

| Prefix | Behavior |
|---|---|
| `gauge-accumulation-` | Snow covers the full gauge, including edges/ticks |
| `wordmark-gauge-accumulation-` | Gauge fills; all lettering stays unchanged |
| `wordmark-gauge-and-snow-accumulation-` | Gauge fills; lower Snow lettering fills partially; x remains clear |

Accumulation takes 8 seconds. The loop holds and fades back to the initial bed
over a 10-second cycle; it never drains downward. One-shot versions freeze at
the end. An uneven granular surface, fixed vector grain and small falling
particles replace the earlier liquid-wave motion. Letter counters stay clear.
The filled pill retains a 0.5-unit rim at 16% opacity.

Native SVG animation has no external scripts, raster textures or font dependency.
Reduced motion and print show the original static master. Repeated inline use
needs unique IDs; separate SVG image/object documents isolate their IDs.

`accumulation-profiles.json` records the original monotonic deposit coordinates.
`browser-check.json` and `controls-check.json` preserve the prior browser review
results. These are visual brand motion, not live snowfall measurements.

If adapting motion to Balanced, use the frozen A-01 transforms from
`../selection.json` for x and the entire Snow group, including clips and the
static fallback. Do not apply the retired Original Alternate A spacing.
