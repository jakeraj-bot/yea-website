(function () {
  var modal = document.getElementById("portal-page-guide");
  if (!modal) return;

  var steps = Array.prototype.slice.call(modal.querySelectorAll("[data-guide-step]"));
  var status = modal.querySelector("[data-guide-status]");
  var prevBtn = modal.querySelector("[data-guide-prev]");
  var nextBtn = modal.querySelector("[data-guide-next]");
  var statusTemplate = (status && status.getAttribute("data-template")) || "Step {current} of {total}";
  var index = 0;
  var lastFocus = null;

  function show(i) {
    if (!steps.length) return;
    index = Math.max(0, Math.min(i, steps.length - 1));
    steps.forEach(function (step, n) {
      step.hidden = n !== index;
    });
    if (status) {
      status.textContent = statusTemplate
        .replace("{current}", String(index + 1))
        .replace("{total}", String(steps.length));
    }
    if (prevBtn) prevBtn.disabled = index <= 0;
    if (nextBtn) {
      nextBtn.textContent = index >= steps.length - 1 ? "Done" : "Next";
    }
  }

  function open() {
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.classList.add("modal-open");
    show(0);
    var closeBtn = modal.querySelector("[data-close-page-guide].btn, .portal-page-guide-header [data-close-page-guide]");
    if (closeBtn) closeBtn.focus();
  }

  function close() {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  document.querySelectorAll("[data-open-page-guide]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      open();
    });
  });
  modal.querySelectorAll("[data-close-page-guide]").forEach(function (button) {
    button.addEventListener("click", close);
  });
  if (prevBtn) {
    prevBtn.addEventListener("click", function () {
      show(index - 1);
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      if (index >= steps.length - 1) {
        close();
        return;
      }
      show(index + 1);
    });
  }
  document.addEventListener("keydown", function (event) {
    if (modal.hidden) return;
    if (event.key === "Escape") close();
    if (event.key === "ArrowRight") show(index + 1);
    if (event.key === "ArrowLeft") show(index - 1);
  });
})();
