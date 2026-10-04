(() => {
  const chartSlideIndex = 4;
  const deck = Reveal.initialize({
    width: 1280,
    height: 720,
    margin: 0,
    minScale: 0.2,
    maxScale: 1.5,
    center: false,
    controls: true,
    controlsTutorial: false,
    progress: true,
    hash: true,
    history: true,
    keyboard: true,
    touch: true,
    transition: "fade",
    backgroundTransition: "fade",
    autoAnimateDuration: 0.7,
    autoAnimateEasing: "ease-out",
    plugins: [RevealNotes]
  });

  window.returnToComparison = () => Reveal.slide(chartSlideIndex);

  deck.then(() => {
    document.querySelectorAll("[data-return-to-story]").forEach((button) => {
      button.addEventListener("click", window.returnToComparison);
    });

    document.querySelectorAll(".demo-frame").forEach((frame) => {
      const attachEscape = () => {
        try {
          const childDocument = frame.contentDocument;
          if (!childDocument) return;
          if (childDocument.__deckEscapeHandler) {
            childDocument.removeEventListener("keydown", childDocument.__deckEscapeHandler, true);
          }
          childDocument.__deckEscapeHandler = (event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              window.returnToComparison();
            }
          };
          childDocument.addEventListener("keydown", childDocument.__deckEscapeHandler, true);
        } catch (error) {
          console.warn("Demo iframe keyboard return is unavailable.", error);
        }
      };
      frame.addEventListener("load", attachEscape);
      if (frame.contentDocument?.readyState === "complete") attachEscape();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && Reveal.getCurrentSlide()?.classList.contains("demo-slide")) {
        window.returnToComparison();
      }
    });

    document.title = "Urban inference can belong near demand — presentation";
  });
})();
