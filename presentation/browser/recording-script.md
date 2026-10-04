# Fixed recording order

Target capture: Chrome content area, 1280 × 720, 16:9. Start the local server and open the deck at `#/`. Keep the pointer clear of captions after each interaction. The target is about six minutes: the original five-minute narration plus concise, visible interaction on the two demo slides.

| Time | Slide | Fixed action and hold |
|---|---|---|
| 00:00–00:35 | Urban inference | Start on the opening image; hold the claim and subtitle. |
| 00:35–01:15 | Density | Press Right once; let the cost and synergy columns settle. |
| 01:15–02:00 | Six systems | Press Right once; show the six links around the inference site. |
| 02:00–02:45 | Evidence funnel | Press Right once. Press Right three more times, with a short beat after each: reveal the screening gate, 8,479 candidates, then the two independent axes. |
| 02:45–03:25 | Two-axis chart | Press Right once; show the four candidates, thresholds, and Astoria / Salem scores. |
| 03:25–04:00 | Site explorer | Press Right once. Let the Astoria record open. In the embedded page, toggle **Former power only** on, pause for the count update, then toggle it off. |
| 04:00–04:30 | Power + connectivity | Press Right once. Select **Comparison**, then **Table**, then **Map** in the embedded preview. Pause over the visible site detail. |
| 04:30–04:35 | Return | Click **Return to comparison** (or press Escape while the iframe has focus). Confirm the two-axis slide is visible. |
| 04:35–05:20 | Astoria diligence | Advance to the next slide. Hold the score-to-record transition, category counts, three wastewater records and caution line. |
| 05:20–06:00 | Conditional strategy | Advance once. Finish on the 2030 / 2040 / 2050 conditional timeline. |

## Repeatable key sequence

Starting at slide 1, move Right for slides 2–5. On the funnel, use Right three times to reveal its three stages before moving to the chart. Move Right to each demo slide. Use its page controls for the demo actions above; the reveal.js arrows at the bottom-right move between slides while the pointer is inside a demo. The **Return to comparison** button returns to the chart. From there, move Right three times (past both demos) to reach Astoria, then Right once for the roadmap. The optional Playwright pass in `scripts/capture-deck.mjs` follows the same order and saves a screenshot at each main and interactive state.

## Presenter checks

- **S** opens presenter view with the active slide notes, elapsed timer and next-slide preview.
- The current cursor should stay over the page margin or be moved off-screen before each hold.
- If external map tiles do not load, keep the embedded controls on screen briefly, then continue; the recorded deck's evidence and caveats are also present on slides 4, 5 and 8.
- The video is a silent screen capture. Read the speaker notes live or record narration separately.
