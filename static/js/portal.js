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

  function syncPortalStickyHeadings() {
    var header = document.querySelector(".portal-header, .site-header");
    if (!header) return;
    var top = Math.ceil(header.getBoundingClientRect().bottom);
    if (top < 0) top = 0;
    document.documentElement.style.setProperty("--portal-sticky-th", top + "px");
  }
  syncPortalStickyHeadings();
  window.addEventListener("resize", syncPortalStickyHeadings);
  window.addEventListener("scroll", syncPortalStickyHeadings, { passive: true });
  if (window.ResizeObserver) {
    var stickyHeader = document.querySelector(".portal-header, .site-header");
    if (stickyHeader) new ResizeObserver(syncPortalStickyHeadings).observe(stickyHeader);
  }

  var slotRows = document.getElementById("dropoff-slot-rows");
  var addSlotRow = document.getElementById("dropoff-add-slot-row");
  var slotCount = document.getElementById("dropoff-slot-row-count");
  if (slotRows && addSlotRow && slotCount) {
    function reindexSlotRows() {
      var rows = slotRows.querySelectorAll(".portal-slot-row");
      rows.forEach(function (row, index) {
        row.setAttribute("data-index", String(index));
        var title = row.querySelector("[data-slot-title]");
        if (title) title.textContent = "Time " + (index + 1);
        var remove = row.querySelector("[data-remove-slot]");
        if (remove) remove.hidden = rows.length < 2;
        row.querySelectorAll("input, select, textarea, label").forEach(function (field) {
          var name = field.getAttribute("name");
          if (name) field.setAttribute("name", name.replace(/_\d+$/, "_" + index));
          if (field.id) field.id = field.id.replace(/-\d+$/, "-" + index);
          var htmlFor = field.getAttribute("for");
          if (htmlFor) field.setAttribute("for", htmlFor.replace(/-\d+$/, "-" + index));
        });
        var timeField = row.querySelector('input[type="time"]');
        if (timeField) timeField.required = index === 0;
      });
      slotCount.value = String(rows.length);
    }
    addSlotRow.addEventListener("click", function () {
      var first = slotRows.querySelector(".portal-slot-row");
      if (!first) return;
      var copy = first.cloneNode(true);
      copy.querySelectorAll("input, select, textarea").forEach(function (field) {
        if (field.type === "checkbox") {
          field.checked = false;
        } else if (field.type !== "hidden") {
          if (field.name && field.name.indexOf("capacity_") === 0) field.value = "10";
          else if (field.name && field.name.indexOf("price_") === 0) field.value = "20.00";
          else field.value = "";
        }
      });
      slotRows.appendChild(copy);
      reindexSlotRows();
    });
    slotRows.addEventListener("click", function (event) {
      var button = event.target.closest("[data-remove-slot]");
      if (!button) return;
      var row = button.closest(".portal-slot-row");
      if (!row || slotRows.querySelectorAll(".portal-slot-row").length < 2) return;
      row.remove();
      reindexSlotRows();
    });
    slotRows.addEventListener("change", function (event) {
      if (!event.target.matches("[data-weekdays-all]")) return;
      var row = event.target.closest(".portal-slot-row");
      if (!row) return;
      row.querySelectorAll('input[type="checkbox"][name^="weekdays_"]').forEach(function (box) {
        box.checked = event.target.checked;
      });
    });
  }
});
