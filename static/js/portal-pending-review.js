window.PortalPendingReview = (function () {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pendingMarkup(newValue, oldValue, phoneSuffix) {
    var suffix = phoneSuffix ? " (" + escapeHtml(phoneSuffix) + ")" : "";
    return (
      '<span class="portal-pending-value">' + escapeHtml(newValue) + suffix + "</span> " +
      '<span class="portal-pending-badge">Pending review</span><br>' +
      '<span class="portal-approved-value">Currently on file: ' + escapeHtml(oldValue) + "</span>"
    );
  }

  function create(options) {
    var storageKey = options.storageKey;
    var banner = document.getElementById(options.bannerId);
    var panel = document.getElementById(options.panelId);
    var tableBody = document.querySelector(options.tableBodySelector);

    function load() {
      try {
        return JSON.parse(sessionStorage.getItem(storageKey) || "[]");
      } catch (e) {
        return [];
      }
    }

    function save(changes) {
      sessionStorage.setItem(storageKey, JSON.stringify(changes));
    }

    function inputValue(input) {
      if (input.type === "checkbox") {
        return input.checked ? "On" : "Off";
      }
      return (input.value || "").trim();
    }

    function applyChange(change) {
      if (change.kind === "emergency") {
        applyEmergency(change);
        return;
      }
      if (change.kind === "medical-note") {
        applyMedicalNote(change);
        return;
      }
      if (change.kind === "password") {
        applyPassword(change);
        return;
      }
      if (change.kind === "autopay-status") {
        applyAutopayStatus(change);
        return;
      }
      if (change.targetId && change.targetId.indexOf("display-secondary-") === 0) {
        var section = document.getElementById("secondary-guardian-section");
        if (section) section.hidden = false;
        document.getElementById("secondary-empty-note")?.remove();
      }
      if (!change.targetId) return;
      var el = document.getElementById(change.targetId);
      if (!el) return;
      if (change.targetId === "secondary-guardian-section") {
        el.hidden = false;
        document.getElementById("secondary-empty-note")?.remove();
      }
      var phoneSuffix = el.getAttribute("data-phone-suffix") || "";
      el.innerHTML = pendingMarkup(change.newValue, change.oldValue, phoneSuffix);
    }

    function applyEmergency(change) {
      var tbody = document.getElementById("display-emergency-contacts");
      if (!tbody) return;
      document.getElementById("no-emergency-contacts-row")?.remove();
      var cellId = "display-emergency-" + change.field + "-" + change.contactIndex;
      var cell = document.getElementById(cellId);
      if (!cell) {
        var row = document.createElement("tr");
        row.setAttribute("data-contact-index", change.contactIndex);
        row.innerHTML =
          '<td id="display-emergency-name-' + change.contactIndex + '"></td>' +
          '<td id="display-emergency-phone-' + change.contactIndex + '"></td>' +
          '<td id="display-emergency-relationship-' + change.contactIndex + '"></td>';
        tbody.appendChild(row);
        cell = document.getElementById(cellId);
      }
      if (!cell) return;
      cell.innerHTML = pendingMarkup(change.newValue, change.oldValue || "Not on file", "");
    }

    function applyMedicalNote(change) {
      var note = document.getElementById("display-medical-notes");
      if (!note) return;
      note.innerHTML = pendingMarkup(change.newValue, change.oldValue, "");
    }

    function applyPassword(change) {
      var el = document.getElementById(change.targetId);
      if (!el) return;
      el.innerHTML = pendingMarkup("Update requested", change.oldValue, "");
    }

    function applyAutopayStatus(change) {
      var el = document.getElementById(change.targetId);
      if (!el) return;
      el.innerHTML = pendingMarkup(change.newValue, change.oldValue, "");
    }

    function appendRow(change) {
      if (!tableBody) return;
      var row = document.createElement("tr");
      row.innerHTML =
        "<td>" + escapeHtml(change.label) + "</td>" +
        "<td>" + escapeHtml(change.oldValue) + "</td>" +
        "<td><strong>" + escapeHtml(change.newValue) + "</strong></td>" +
        '<td><span class="portal-pending-badge">Pending review</span></td>';
      tableBody.appendChild(row);
    }

    function render(changes) {
      if (!changes.length) {
        if (banner) banner.hidden = true;
        if (panel) panel.hidden = true;
        return;
      }
      if (tableBody) tableBody.innerHTML = "";
      changes.forEach(function (change) {
        applyChange(change);
        appendRow(change);
      });
      if (banner) banner.hidden = false;
      if (panel) panel.hidden = false;
    }

    function upsert(change) {
      var changes = load().filter(function (item) {
        return item.label !== change.label;
      });
      changes.push(change);
      save(changes);
      render(changes);
      return changes;
    }

    function syncInput(changes, input) {
      var label = input.getAttribute("data-label");
      if (!label) return changes;
      var oldValue = input.getAttribute("data-original") || "";
      var newValue = inputValue(input);
      changes = changes.filter(function (item) {
        return item.label !== label;
      });
      if (input.type === "checkbox") {
        var originalOn = input.getAttribute("data-original") === "On";
        if (input.checked === originalOn) return changes;
        oldValue = originalOn ? "On" : "Off";
        newValue = input.checked ? "On" : "Off";
      } else {
        if (!newValue && !oldValue) return changes;
        if (newValue === oldValue) return changes;
      }
      changes.push({
        targetId: input.getAttribute("data-target") || "",
        label: label,
        oldValue: oldValue || "Not on file",
        newValue: newValue,
        kind: input.getAttribute("data-kind") || "field",
      });
      return changes;
    }

    function collectFromContainer(container) {
      var changes = [];
      container.querySelectorAll("[data-label]").forEach(function (input) {
        changes = syncInput(changes, input);
      });
      return changes;
    }

    function mergeFromContainer(container) {
      var existing = load();
      var incoming = collectFromContainer(container);
      var labels = {};
      container.querySelectorAll("[data-label]").forEach(function (input) {
        labels[input.getAttribute("data-label")] = true;
      });
      existing = existing.filter(function (item) {
        return !labels[item.label];
      });
      incoming.forEach(function (change) {
        existing.push(change);
      });
      save(existing);
      render(existing);
      return existing;
    }

    function syncEmergency(changes) {
      changes = changes.filter(function (item) {
        return item.kind !== "emergency";
      });
      var rows = document.querySelectorAll("#emergency-contact-rows .portal-emergency-edit-row");
      var fieldLabels = { name: "Name", phone: "Phone", relationship: "Relationship" };
      rows.forEach(function (row, index) {
        row.querySelectorAll(".portal-emergency-input").forEach(function (input) {
          var oldValue = input.getAttribute("data-original") || "";
          var newValue = input.value.trim();
          if (!newValue && !oldValue) return;
          if (oldValue === newValue) return;
          var field = input.getAttribute("data-field");
          var isNew = !oldValue && newValue;
          changes.push({
            targetId: "display-emergency-" + field + "-" + index,
            label: isNew
              ? "Emergency contact " + (index + 1) + " — New contact (" + fieldLabels[field] + ")"
              : "Emergency contact " + (index + 1) + " — " + fieldLabels[field],
            oldValue: oldValue || "Not on file",
            newValue: newValue,
            kind: "emergency",
            contactIndex: index,
            field: field,
          });
        });
      });
      return changes;
    }

    function collectFromForm(form) {
      var changes = [];
      form.querySelectorAll("[data-label]").forEach(function (input) {
        changes = syncInput(changes, input);
      });
      changes = syncEmergency(changes);
      return changes;
    }

    return {
      load: load,
      save: save,
      render: render,
      upsert: upsert,
      collectFromForm: collectFromForm,
      collectFromContainer: collectFromContainer,
      mergeFromContainer: mergeFromContainer,
      syncInput: syncInput,
    };
  }

  return { create: create };
})();
