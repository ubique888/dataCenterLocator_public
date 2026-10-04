# Browser presentation

The reveal.js version is a 16:9 browser presentation built from the existing seven-slide story, speaker notes and validated figures. The two project HTML demos run inside the deck as interactive slides. The original PPTX and PDF remain separate files in `presentation/output/`.

## Play locally

From the `infrastructure-inheritance-symbiosis` project directory:

```sh
node presentation/browser/serve.mjs
```

Open <http://127.0.0.1:4173/presentation/browser/>. Use the arrow keys, Space, or the on-screen arrows to move through the slides. On either demo slide, click **Return to comparison** or press **Escape** to return to the two-axis slide. Press **S** to open the reveal.js speaker view with notes and a clock. The slide canvas is authored at 1280 × 720 (16:9); full-screen playback gives the cleanest framing.

To use another port, run `node presentation/browser/serve.mjs --port 4174`.

## Network needs

The deck loads reveal.js and fonts from public CDNs. Both project demos also load Leaflet, map tiles and, in places, public map-service geometry. A network connection is needed for those assets. If a map provider is unavailable, the filters and record data remain in the embedded page; the deck retains the validated chart and numbers independently of the map.

## Fixed-order recording script

The click-by-click order and target timing are in [recording-script.md](./recording-script.md). Follow that sequence with the screen recorder you normally use. The script keeps the silent interaction segment to a fixed order and returns from both demos to the two-axis comparison before Astoria.

```sh
node presentation/browser/scripts/capture-deck.mjs
```

This optional Playwright pass opens and verifies the speaker view, then saves 1280 × 720 screenshots for each slide and interaction state under `presentation/browser/.qa/visual-review/`. It expects the local server above to be running and an installed Chrome channel. Set `BROWSER_CHANNEL` to another installed Playwright Chromium channel if needed. If `playwright` is not resolvable from this project, point `PLAYWRIGHT_MODULE` at its `index.mjs` entry.

The demo opens Astoria (EPA site 40157) so a recording has a consistent starting record. This is an optional query-string entry point; opening either HTML demo without `?site=...` still starts in its existing default view.

## Source correspondence

- Slides 1–5 and 8–9 carry the original seven-slide narrative and the original seven speaker notes.
- Slides 6–7 embed `outputs/infrastructure_inheritance_symbiosis.html` and `outputs/power_connectivity_preview.html`.
- The comparison chart retains the original 60 inheritance / 75 symbiosis thresholds and the Astoria, Salem, Indian Point and Davis Street values.
- The Astoria page retains the independently recounted 37 FRS IDs, 34 coordinate groups, category counts and the unverified heat-use caveats.
