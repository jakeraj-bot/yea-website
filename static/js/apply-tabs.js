(function () {
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
  }

  function initApplyTabs() {
    document.querySelectorAll("[data-apply-tabs]").forEach(function (root) {
      var tabs = root.querySelectorAll("[data-tab-target]");
      if (!tabs.length) return;

      tabs.forEach(function (tab) {
        tab.addEventListener("click", function (event) {
          event.preventDefault();
          activateTab(root, tab.getAttribute("data-tab-target"));
        });
      });

      var firstError = root.querySelector(".errorlist");
      if (firstError) {
        var panel = firstError.closest("[data-tab-panel]");
        if (panel) {
          activateTab(root, panel.getAttribute("data-tab-panel"));
        }
      }
    });
  }

  window.initApplyTabs = initApplyTabs;
})();
