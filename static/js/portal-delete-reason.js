(function () {
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var modal = document.getElementById("portal-delete-reason-modal");
    if (!modal) return;
    var promptEl = document.getElementById("portal-delete-reason-prompt");
    var input = document.getElementById("portal-delete-reason-input");
    var errorEl = document.getElementById("portal-delete-reason-error");
    var cancelBtn = document.getElementById("portal-delete-reason-cancel");
    var confirmBtn = document.getElementById("portal-delete-reason-confirm");
    var pendingForm = null;

    function closeModal() {
      modal.hidden = true;
      pendingForm = null;
      if (input) input.value = "";
      if (errorEl) errorEl.hidden = true;
    }

    function openModal(form) {
      pendingForm = form;
      var message = form.getAttribute("data-delete-message") || "This cannot be undone.";
      if (promptEl) promptEl.textContent = message + " The reason is saved on that person’s activity log.";
      if (input) input.value = "";
      if (errorEl) errorEl.hidden = true;
      modal.hidden = false;
      if (input) input.focus();
    }

    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form || !form.matches || !form.matches("form.js-need-delete-reason")) return;
      if (form.getAttribute("data-delete-ready") === "1") {
        form.removeAttribute("data-delete-ready");
        return;
      }
      event.preventDefault();
      openModal(form);
    });

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        closeModal();
      });
    }

    modal.addEventListener("click", function (event) {
      if (event.target === modal) closeModal();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !modal.hidden) {
        closeModal();
      }
    });

    if (confirmBtn) {
      confirmBtn.addEventListener("click", function () {
        var reason = (input && input.value ? input.value : "").trim();
        if (!reason) {
          if (errorEl) errorEl.hidden = false;
          if (input) input.focus();
          return;
        }
        if (!pendingForm) return;
        var hidden = pendingForm.querySelector('input[name="delete_reason"]');
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "delete_reason";
          pendingForm.appendChild(hidden);
        }
        hidden.value = reason;
        pendingForm.setAttribute("data-delete-ready", "1");
        var formToSubmit = pendingForm;
        closeModal();
        if (typeof formToSubmit.requestSubmit === "function") {
          formToSubmit.requestSubmit();
        } else {
          formToSubmit.submit();
        }
      });
    }
  });
})();
