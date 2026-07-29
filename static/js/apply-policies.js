(function () {
  function initPolicyNav() {
    var root = document.getElementById("apply-policies");
    if (!root) return;

    var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-tab-target]"));
    var prevBtn = document.getElementById("policy-prev-btn");
    var nextBtn = document.getElementById("policy-next-btn");
    if (!tabs.length) return;

    function activeIndex() {
      return tabs.findIndex(function (tab) {
        return tab.classList.contains("is-active");
      });
    }

    function goTo(index) {
      var tab = tabs[index];
      if (!tab) return;
      tab.click();
      if (prevBtn) prevBtn.disabled = index <= 0;
      if (nextBtn) nextBtn.disabled = index >= tabs.length - 1;
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        if (prevBtn) prevBtn.disabled = index <= 0;
        if (nextBtn) nextBtn.disabled = index >= tabs.length - 1;
      });
    });

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        goTo(Math.max(0, activeIndex() - 1));
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        goTo(Math.min(tabs.length - 1, activeIndex() + 1));
      });
    }

    goTo(Math.max(0, activeIndex()));
  }

  document.addEventListener("DOMContentLoaded", initPolicyNav);
})();
