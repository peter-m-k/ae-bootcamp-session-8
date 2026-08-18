/**
 * Light/dark mode toggle. The initial mode is applied inline in <head>
 * (see templates/index.html) to avoid a flash of the wrong theme.
 */
(function () {
  function currentTheme() {
    return document.documentElement.getAttribute("data-bs-theme") || "light";
  }

  function updateButton(theme) {
    const button = document.getElementById("theme-toggle");
    if (!button) return;
    button.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    button.setAttribute("aria-pressed", theme === "dark");
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    localStorage.setItem("theme", theme);
    updateButton(theme);
  }

  document.addEventListener("DOMContentLoaded", () => {
    updateButton(currentTheme());
    const button = document.getElementById("theme-toggle");
    if (button) {
      button.addEventListener("click", () => {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }
  });
})();
