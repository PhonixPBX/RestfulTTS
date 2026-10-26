/*
 * RestfulTTS UI glue (no inline scripts: the CSP only allows 'self').
 * - sends the CSRF token with every htmx request
 * - small helpers driven by data-* attributes
 */
(function () {
  "use strict";

  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

  document.addEventListener("htmx:config:request", (evt) => {
    const ctx = evt.detail && evt.detail.ctx;
    if (ctx && ctx.request && ctx.request.headers && csrf()) {
      ctx.request.headers["X-CSRF-Token"] = csrf();
    }
  });

  // <input type="range" data-output="#id"> shows its value in #id
  document.addEventListener("input", (evt) => {
    const sel = evt.target.dataset && evt.target.dataset.output;
    const out = sel && document.querySelector(sel);
    if (out) out.textContent = Number(evt.target.value).toFixed(2).replace(/0$/, "") + "×";
  });

  document.addEventListener("focusin", (evt) => {
    if (evt.target.matches && evt.target.matches("[data-select-on-focus]")) evt.target.select();
  });
})();
