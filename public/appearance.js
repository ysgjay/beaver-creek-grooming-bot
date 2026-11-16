/* Run in the head before styles load: system appearance, with a saved per-device choice. */
(() => {
  "use strict";
  const key = "chair0.appearance", choices = ["system", "light", "dark"];
  const device = matchMedia("(prefers-color-scheme: dark)");
  const normalize = (value) => choices.includes(value) ? value : "system";
  let preference = "system";
  try { preference = normalize(localStorage.getItem(key)); } catch (_) {}
  const scheme = () => preference === "system" ? (device.matches ? "dark" : "light") : preference;
  function apply() {
    const root = document.documentElement, previous = root.dataset.appearance, next = scheme();
    root.dataset.theme = "bluebird";
    root.dataset.material = "frost";
    root.dataset.appearance = next;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = next === "dark" ? "#071b2e" : "#dcebfa";
    const status = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
    if (status) status.content = next === "dark" ? "black-translucent" : "default";
    document.dispatchEvent(new CustomEvent("appearancechange", { detail: { preference, scheme: next, changed: previous !== next } }));
  }
  window.Appearance = {
    preference: () => preference,
    scheme,
    set(value) {
      preference = normalize(value);
      try { localStorage.setItem(key, preference); } catch (_) {}
      apply();
    },
  };
  device.addEventListener("change", () => { if (preference === "system") apply(); });
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) { preference = normalize(event.newValue); apply(); }
  });
  apply();
})();
