(function () {
  function activateErrorTab(firstError) {
    if (!firstError || !window.initApplyTabs) return;
    var panel = firstError.closest("[data-tab-panel]");
    if (!panel) return;
    var root = panel.closest("[data-apply-tabs]");
    var panelId = panel.getAttribute("data-tab-panel");
    if (!root || !panelId) return;

    root.querySelectorAll("[data-tab-target]").forEach(function (tab) {
      var active = tab.getAttribute("data-tab-target") === panelId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    root.querySelectorAll("[data-tab-panel]").forEach(function (item) {
      var active = item.getAttribute("data-tab-panel") === panelId;
      item.classList.toggle("is-active", active);
      if (active) item.removeAttribute("hidden");
      else item.setAttribute("hidden", "");
    });
  }

  function initApplyFormErrors() {
    var firstError = document.querySelector(".apply-form .errorlist");
    if (firstError) activateErrorTab(firstError);

    var banner = document.getElementById("apply-error-banner");
    if (banner) {
      requestAnimationFrame(function () {
        banner.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    if (!firstError) return;
    var group = firstError.closest(".form-group, .emergency-contact-block, .policy-sign-block");
    var input = group && group.querySelector("input, select, textarea");
    if (!input || input.closest("[hidden]")) return;
    setTimeout(function () {
      try {
        input.focus({ preventScroll: true });
      } catch (e) {
        input.focus();
      }
    }, 200);
  }

  function initApplyFormSubmit() {
    document.querySelectorAll(".apply-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        var btn = form.querySelector('.apply-actions button[type="submit"]');
        if (!btn || btn.disabled) return;
        if (typeof form.checkValidity === "function" && !form.checkValidity()) {
          return;
        }
        btn.disabled = true;
        btn.setAttribute("aria-busy", "true");
        btn.classList.add("is-loading");
        var loadingText = btn.getAttribute("data-loading-text") || "Please wait…";
        btn.dataset.originalText = btn.textContent;
        btn.textContent = loadingText;
      });
    });
  }

  window.initApplyForm = function () {
    initApplyFormSubmit();
    initApplyFormErrors();
  };
})();
