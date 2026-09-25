/* ============================================================
   Theme switcher — light / dark with persistence
   Default is always LIGHT. Users can opt in to dark mode.
   ============================================================ */
(function () {
  "use strict";

  const STORAGE_KEY = "pypdf-theme";
  const root = document.documentElement;

  function currentTheme() {
    return root.getAttribute("data-theme") || "light";
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
    updateToggles(theme);
  }

  function toggleTheme() {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  }

  function updateToggles(theme) {
    document.querySelectorAll(".theme-toggle").forEach((btn) => {
      const isDark = theme === "dark";
      btn.innerHTML = isDark ? "☀️" : "🌙";
      btn.title = isDark ? "Switch to light mode" : "Switch to dark mode";
      btn.setAttribute("aria-label", btn.title);
    });
  }

  function wireButtons() {
    document.querySelectorAll(".theme-toggle").forEach((btn) => {
      btn.addEventListener("click", toggleTheme);
    });
    updateToggles(currentTheme());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireButtons);
  } else {
    wireButtons();
  }
})();
