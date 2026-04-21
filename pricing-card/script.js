(function () {
  var wrap = document.querySelector(".pricing-float-wrap");
  var card = document.querySelector(".pricing-card");
  var badge = document.querySelector("[data-animate-badge]");
  var cta = document.querySelector("[data-animate-cta]");
  if (!wrap || !card || !window.anime) return;

  var floatingAnim = null;

  function startFloating() {
    if (floatingAnim) floatingAnim.pause();
    floatingAnim = anime({
      targets: wrap,
      translateY: [0, -4, 0],
      duration: 4500,
      easing: "easeInOutSine",
      loop: true,
    });
  }

  /* 1) Card entrance */
  anime({
    targets: card,
    opacity: [0, 1],
    translateY: [20, 0],
    scale: [0.96, 1],
    duration: 900,
    easing: "easeOutCubic",
    complete: function () {
      card.style.willChange = "auto";
      startFloating();
    },
  });

  /* 3) Badge fades in slightly after card */
  if (badge) {
    anime({
      targets: badge,
      opacity: [0, 1],
      translateY: [6, 0],
      duration: 500,
      delay: 600,
      easing: "easeOutQuad",
    });
  }

  /* 2) Button hover — scale ~1.04 */
  if (cta) {
    cta.addEventListener("mouseenter", function () {
      anime.remove(cta);
      anime({
        targets: cta,
        scale: 1.04,
        duration: 220,
        easing: "easeOutQuad",
      });
    });
    cta.addEventListener("mouseleave", function () {
      anime.remove(cta);
      anime({
        targets: cta,
        scale: 1,
        duration: 220,
        easing: "easeOutQuad",
      });
    });
  }
})();
