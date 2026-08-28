(function () {
  function strings() {
    var el = document.getElementById("apply-ui-strings");
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return {};
    }
  }

  function activateTab(root, panelId) {
    var tabs = root.querySelectorAll("[data-tab-target]");
    var panels = root.querySelectorAll("[data-tab-panel]");

    tabs.forEach(function (tab) {
      var active = tab.getAttribute("data-tab-target") === panelId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });

    panels.forEach(function (panel) {
      var active = panel.getAttribute("data-tab-panel") === panelId;
      panel.classList.toggle("is-active", active);
      if (active) {
        panel.removeAttribute("hidden");
      } else {
        panel.setAttribute("hidden", "");
      }
    });

    var activeTab = root.querySelector("[data-tab-target].is-active");
    if (activeTab && activeTab.scrollIntoView) {
      activeTab.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
    updateSectionChrome(root);
  }

  function tabList(root) {
    return Array.prototype.slice.call(root.querySelectorAll("[data-tab-target]"));
  }

  function activeIndex(root) {
    var tabs = tabList(root);
    return tabs.findIndex(function (tab) {
      return tab.classList.contains("is-active");
    });
  }

  function namedNext(root) {
    var copy = strings();
    var tabs = tabList(root);
    var idx = activeIndex(root);
    var next = tabs[idx + 1];
    var name = next ? (next.textContent || "").trim() : "";
    if (name && copy.nextNamed) return copy.nextNamed.replace("{name}", name);
    return copy.nextSection || "Next section";
  }

  function updateSectionChrome(root) {
    var tabs = tabList(root);
    var idx = Math.max(0, activeIndex(root));
    var prev = root.querySelector("[data-section-prev]");
    var next = root.querySelector("[data-section-next]");
    if (prev) prev.disabled = idx <= 0;
    if (next) {
      next.disabled = idx >= tabs.length - 1;
      next.textContent = namedNext(root);
    }

    var form = root.closest("form");
    var submit = form && form.querySelector(".apply-actions button[type='submit']");
    if (!submit || submit.classList.contains("is-loading")) return;
    var copy = strings();
    if (idx < tabs.length - 1) {
      submit.textContent = namedNext(root);
      submit.dataset.sectionAdvance = "1";
    } else {
      submit.textContent = submit.getAttribute("data-continue-label") || copy.continueLabel || "Continue";
      submit.dataset.sectionAdvance = "";
    }
  }

  function goTo(root, index) {
    var tabs = tabList(root);
    var tab = tabs[index];
    if (!tab) return;
    tab.click();
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function ensureHint(root) {
    if (root.querySelector(".apply-section-hint")) return;
    var copy = strings();
    if (!copy.sectionHint) return;
    var hint = document.createElement("p");
    hint.className = "apply-section-hint";
    hint.textContent = copy.sectionHint;
    var nav = root.querySelector(".apply-section-tabs");
    if (nav) nav.parentNode.insertBefore(hint, nav);
  }

  function ensureToolbar(root) {
    ensureHint(root);
    if (root.querySelector(".apply-section-toolbar")) return;
    if (root.querySelector(".apply-policy-toolbar")) return;
    var copy = strings();
    var bar = document.createElement("div");
    bar.className = "apply-section-toolbar";
    bar.innerHTML =
      '<button type="button" class="btn btn-secondary" data-section-prev></button>' +
      '<button type="button" class="btn btn-primary" data-section-next></button>';
    var prev = bar.querySelector("[data-section-prev]");
    var next = bar.querySelector("[data-section-next]");
    prev.textContent = copy.prevSection || "Previous section";
    next.textContent = copy.nextSection || "Next section";
    root.appendChild(bar);

    prev.addEventListener("click", function () {
      goTo(root, Math.max(0, activeIndex(root) - 1));
    });
    next.addEventListener("click", function () {
      var tabs = tabList(root);
      goTo(root, Math.min(tabs.length - 1, activeIndex(root) + 1));
    });
  }

  function interceptContinue(root) {
    var form = root.closest("form");
    var submit = form && form.querySelector(".apply-actions button[type='submit']");
    if (!form || !submit || submit.dataset.sectionContinueBound) return;
    submit.dataset.sectionContinueBound = "1";
    submit.addEventListener("click", function (event) {
      if (submit.dataset.sectionAdvance !== "1") return;
      event.preventDefault();
      var panel = root.querySelector("[data-tab-panel].is-active");
      var invalid = panel && panel.querySelector(":invalid");
      if (invalid) {
        if (typeof invalid.reportValidity === "function") invalid.reportValidity();
        return;
      }
      var tabs = tabList(root);
      goTo(root, Math.min(tabs.length - 1, activeIndex(root) + 1));
    });
  }

  function initApplyTabs() {
    document.querySelectorAll("[data-apply-tabs]").forEach(function (root) {
      var tabs = tabList(root);
      if (!tabs.length) return;

      tabs.forEach(function (tab) {
        tab.addEventListener("click", function (event) {
          event.preventDefault();
          activateTab(root, tab.getAttribute("data-tab-target"));
        });
      });

      ensureToolbar(root);
      interceptContinue(root);

      var firstError = root.querySelector(".errorlist");
      if (firstError) {
        var panel = firstError.closest("[data-tab-panel]");
        if (panel) {
          activateTab(root, panel.getAttribute("data-tab-panel"));
          return;
        }
      }
      updateSectionChrome(root);
    });
  }

  window.initApplyTabs = initApplyTabs;
})();
