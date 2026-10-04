# Visual review

- Viewport: 1280 × 720 (16:9), independent headless Chrome.
- Reviewed all seven narrative slides, the three visible funnel stages, both embedded demos, three connectivity views, and the return-to-comparison state. Screenshots are in this folder; [contact sheet](./contact-sheet.png) shows the nine primary slides.
- Speaker view opened with **S** and displayed the first slide's note. All seven original speaker-note bodies were compared against `presentation/speaker_notes.md` and match verbatim. The two demo pages have short operational notes.
- Interaction review: the site filter toggles; the connectivity demo switches among Map, Compare and Table; both **Return to comparison** and Escape from an iframe return to the candidate chart.
- Browser console: independent Chrome completed the capture pass without page errors. The Codex in-app preview logs a `MutationObserver` non-Node warning when multiple iframes are open; the page still renders. This matches the [Codex in-app browser issue](https://github.com/openai/codex/issues/37941), and did not reproduce in independent Chrome.
- The source `presentation/output/presentation.pptx` was not edited. SHA-256 before and after review: `a39997dce9c934bafac0a1328326e34296a687ea5787ff0a181a22198b399fc1`.
