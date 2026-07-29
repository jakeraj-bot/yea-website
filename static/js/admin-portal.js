(function () {
  function toggleStaffUnits() {
    var role = document.getElementById("staff-role");
    var unitGroup = document.getElementById("staff-units-group");
    var primaryUnit = document.getElementById("staff-primary-unit-group");
    if (!role || !unitGroup) return;
    var isAdmin = role.value === "Portal admin";
    unitGroup.hidden = isAdmin;
    if (primaryUnit) primaryUnit.hidden = isAdmin;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var role = document.getElementById("staff-role");
    if (role) {
      role.addEventListener("change", toggleStaffUnits);
      toggleStaffUnits();
    }

    document.querySelectorAll("[data-rich-toolbar]").forEach(function (toolbar) {
      var targetId = toolbar.getAttribute("data-rich-toolbar");
      var target = document.getElementById(targetId);
      if (!target) return;
      toolbar.querySelectorAll("button[data-cmd]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          var cmd = btn.getAttribute("data-cmd");
          var val = btn.getAttribute("data-val") || null;
          document.execCommand(cmd, false, val);
          target.focus();
        });
      });
      var form = toolbar.closest("form");
      if (form) {
        form.addEventListener("submit", function () {
          var hidden = form.querySelector('input[name="body_html"]');
          if (hidden) hidden.value = target.innerHTML;
          var plain = form.querySelector('textarea[name="body"]');
          if (plain) plain.value = target.innerText;
        });
      }
    });

    document.querySelectorAll(".portal-yesno-toggle input").forEach(function (input) {
      input.addEventListener("change", function () {
        var label = input.closest(".portal-yesno-toggle");
        if (label) {
          var span = label.querySelector("[data-yesno-label]");
          if (span) span.textContent = input.checked ? "Yes" : "No";
        }
      });
    });
  });
})();
