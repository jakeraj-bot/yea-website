document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".portal-back-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const fallback = button.getAttribute("data-fallback");
      const referrer = document.referrer;
      const sameSite =
        referrer &&
        (referrer.startsWith(window.location.origin) ||
          referrer.includes(window.location.host));

      if (sameSite && window.history.length > 1) {
        window.history.back();
        return;
      }

      if (fallback) {
        window.location.href = fallback;
      } else if (window.history.length > 1) {
        window.history.back();
      }
    });
  });

  window.portalPreviewToast = function (message) {
    var existing = document.querySelector(".portal-preview-toast");
    if (existing) existing.remove();
    var toast = document.createElement("div");
    toast.className = "portal-preview-toast";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(function () {
      toast.classList.add("is-visible");
    });
    setTimeout(function () {
      toast.classList.remove("is-visible");
      setTimeout(function () {
        toast.remove();
      }, 300);
    }, 3200);
  };

  document.querySelectorAll("[data-preview-panel]").forEach(function (button) {
    button.addEventListener("click", function () {
      var panelId = button.getAttribute("data-preview-panel");
      var panel = document.getElementById(panelId);
      if (panel) panel.hidden = !panel.hidden;
    });
  });

  document.querySelectorAll(".portal-preview-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var message = form.getAttribute("data-preview-message") || "Saved for preview.";
      window.portalPreviewToast(message);
      var panel = form.closest(".portal-panel");
      if (panel && panel.id !== "edit-profile-panel") panel.hidden = true;
    });
  });

  document.querySelectorAll(".portal-preview-action").forEach(function (button) {
    button.addEventListener("click", function () {
      window.portalPreviewToast(button.getAttribute("data-preview-message") || "Updated for preview.");
    });
  });
});
