/**
 * Mobile drawer, service worker registration.
 */
(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("sidebar-toggle");
    const sidebar = document.querySelector(".sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");

    function closeDrawer() {
      if (sidebar) sidebar.classList.remove("sidebar--open");
      if (backdrop) backdrop.classList.remove("is-visible");
      document.body.classList.remove("drawer-open");
    }

    function openDrawer() {
      if (sidebar) sidebar.classList.add("sidebar--open");
      if (backdrop) backdrop.classList.add("is-visible");
      document.body.classList.add("drawer-open");
    }

    if (toggle && sidebar) {
      toggle.addEventListener("click", () => {
        if (sidebar.classList.contains("sidebar--open")) closeDrawer();
        else openDrawer();
      });
    }
    if (backdrop) {
      backdrop.addEventListener("click", closeDrawer);
    }

    document.querySelectorAll(".sidebar .nav-link").forEach((a) => {
      a.addEventListener("click", () => {
        if (window.matchMedia("(max-width: 899px)").matches) closeDrawer();
      });
    });

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  });
})();
