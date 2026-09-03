(function () {
  var STORAGE_KEY = "yea-staff-families-prefs-v5";
  var table = document.getElementById("families-table");
  if (!table) return;

  var tbody = document.getElementById("families-table-body");
  var rows = Array.prototype.slice.call(tbody.querySelectorAll("[data-family-row]"));
  var searchInput = document.getElementById("families-search");
  var filterSelect = document.getElementById("families-filter");
  var unitFilterSelect = document.getElementById("families-unit-filter");
  var sortSelect = document.getElementById("families-sort");
  var pageSizeSelect = document.getElementById("families-page-size");
  var summaryEl = document.getElementById("families-results-summary");
  var paginationEl = document.getElementById("families-pagination");
  var emptyState = document.getElementById("families-empty-state");
  var colToggles = document.querySelectorAll("[data-col-toggle]");

  var state = {
    search: "",
    filter: "all",
    unit: "all",
    sort: "name-asc",
    pageSize: "25",
    page: 1,
    columns: {},
  };

  function loadPrefs() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      Object.assign(state, saved);
    } catch (e) {
      /* ignore */
    }
    colToggles.forEach(function (input) {
      var col = input.getAttribute("data-col-toggle");
      if (state.columns && Object.prototype.hasOwnProperty.call(state.columns, col)) {
        input.checked = !!state.columns[col];
      } else {
        state.columns[col] = input.checked;
      }
    });
    searchInput.value = state.search || "";
    filterSelect.value = state.filter || "all";
    if (unitFilterSelect) unitFilterSelect.value = state.unit || "all";
    sortSelect.value = state.sort || "name-asc";
    pageSizeSelect.value = state.pageSize || "25";
  }

  function savePrefs() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function parseBalance(value) {
    var num = parseFloat(String(value).replace(/[^0-9.-]/g, ""));
    return isNaN(num) ? 0 : num;
  }

  function uniqueFamilyCount(list) {
    var slugs = new Set();
    list.forEach(function (row) {
      slugs.add(row.getAttribute("data-slug"));
    });
    return slugs.size;
  }

  function rowMatchesFilter(row) {
    if (unitFilterSelect && state.unit && state.unit !== "all") {
      var unitSlug = row.getAttribute("data-unit-slug") || "";
      var unitName = row.getAttribute("data-unit") || "";
      if (unitSlug !== state.unit && unitName.indexOf(state.unit) === -1) {
        return false;
      }
    }
    var status = row.getAttribute("data-status") || "";
    var billing = row.getAttribute("data-billing") || "";
    var balance = parseBalance(row.getAttribute("data-family-balance") || row.getAttribute("data-balance"));
    switch (state.filter) {
      case "active":
        return status.indexOf("active") !== -1 && status.indexOf("pending") === -1;
      case "pending-enrollment":
        return status.indexOf("pending enrollment") !== -1;
      case "past-due":
        return balance > 0;
      case "4cs":
        return billing.indexOf("4cs") !== -1;
      case "private-pay":
        return billing.indexOf("private") !== -1;
      case "pending-membership":
        return status.indexOf("pending membership") !== -1;
      case "no-application":
        return row.getAttribute("data-has-application") === "0";
      case "no-login":
        return row.getAttribute("data-has-login") === "0";
      case "suspended":
        return status.indexOf("suspended") !== -1;
      default:
        return true;
    }
  }

  function rowMatchesSearch(row) {
    var q = (state.search || "").trim().toLowerCase();
    if (!q) return true;
    var haystack = [
      row.getAttribute("data-unit"),
      row.getAttribute("data-name"),
      row.getAttribute("data-contact"),
      row.getAttribute("data-child-name"),
      row.getAttribute("data-school"),
      row.getAttribute("data-program"),
      row.getAttribute("data-billing"),
      row.getAttribute("data-status"),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(q) !== -1;
  }

  function sortRows(list) {
    var sorted = list.slice();
    sorted.sort(function (a, b) {
      var nameA = a.getAttribute("data-name") || "";
      var nameB = b.getAttribute("data-name") || "";
      var childA = a.getAttribute("data-child-name") || "";
      var childB = b.getAttribute("data-child-name") || "";
      var unitA = a.getAttribute("data-unit") || "";
      var unitB = b.getAttribute("data-unit") || "";
      var contactA = a.getAttribute("data-contact") || "";
      var contactB = b.getAttribute("data-contact") || "";
      var familyBalA = parseBalance(a.getAttribute("data-family-balance") || a.getAttribute("data-balance"));
      var familyBalB = parseBalance(b.getAttribute("data-family-balance") || b.getAttribute("data-balance"));
      var childBalA = parseBalance(a.getAttribute("data-child-balance"));
      var childBalB = parseBalance(b.getAttribute("data-child-balance"));
      switch (state.sort) {
        case "name-desc":
          return nameB.localeCompare(nameA) || childA.localeCompare(childB);
        case "unit-asc":
          return unitA.localeCompare(unitB) || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "unit-desc":
          return unitB.localeCompare(unitA) || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "balance-desc":
          return familyBalB - familyBalA || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "balance-asc":
          return familyBalA - familyBalB || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "child-balance-desc":
          return childBalB - childBalA || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "child-balance-asc":
          return childBalA - childBalB || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        case "contact-asc":
          return contactA.localeCompare(contactB) || nameA.localeCompare(nameB) || childA.localeCompare(childB);
        default:
          return nameA.localeCompare(nameB) || childA.localeCompare(childB);
      }
    });
    return sorted;
  }

  function applyColumnVisibility() {
    Object.keys(state.columns).forEach(function (col) {
      var visible = state.columns[col];
      table.querySelectorAll('[data-col="' + col + '"]').forEach(function (cell) {
        cell.hidden = !visible;
      });
    });
  }

  function renderPagination(total, pageCount) {
    paginationEl.innerHTML = "";
    if (pageCount <= 1) return;

    var prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn btn-secondary btn-sm";
    prev.textContent = "Previous";
    prev.disabled = state.page <= 1;
    prev.addEventListener("click", function () {
      state.page = Math.max(1, state.page - 1);
      savePrefs();
      render();
    });

    var next = document.createElement("button");
    next.type = "button";
    next.className = "btn btn-secondary btn-sm";
    next.textContent = "Next";
    next.disabled = state.page >= pageCount;
    next.addEventListener("click", function () {
      state.page = Math.min(pageCount, state.page + 1);
      savePrefs();
      render();
    });

    var label = document.createElement("span");
    label.className = "portal-families-page-label";
    label.textContent = "Page " + state.page + " of " + pageCount;

    paginationEl.appendChild(prev);
    paginationEl.appendChild(label);
    paginationEl.appendChild(next);
  }

  function render() {
    var matched = sortRows(rows.filter(function (row) {
      return rowMatchesFilter(row) && rowMatchesSearch(row);
    }));

    var pageSize = state.pageSize === "all" ? matched.length : parseInt(state.pageSize, 10);
    if (!pageSize || pageSize < 1) pageSize = matched.length || 1;
    var pageCount = Math.max(1, Math.ceil(matched.length / pageSize));
    if (state.page > pageCount) state.page = pageCount;
    if (state.page < 1) state.page = 1;

    var start = (state.page - 1) * pageSize;
    var end = start + pageSize;
    var visibleSet = new Set(matched.slice(start, end));

    rows.forEach(function (row) {
      row.hidden = !visibleSet.has(row);
    });

    matched.forEach(function (row) {
      tbody.appendChild(row);
    });

    var showingFrom = matched.length ? start + 1 : 0;
    var showingTo = Math.min(end, matched.length);
    var familyCount = uniqueFamilyCount(matched);
    summaryEl.textContent =
      "Showing " +
      showingFrom +
      "–" +
      showingTo +
      " of " +
      matched.length +
      " children (" +
      familyCount +
      " families)" +
      (matched.length !== rows.length ? " (filtered from " + rows.length + " children)" : "");

    emptyState.hidden = matched.length > 0;
    table.hidden = matched.length === 0;
    renderPagination(matched.length, pageCount);
    applyColumnVisibility();
  }

  searchInput.addEventListener("input", function () {
    state.search = searchInput.value;
    state.page = 1;
    savePrefs();
    render();
  });

  filterSelect.addEventListener("change", function () {
    state.filter = filterSelect.value;
    state.page = 1;
    savePrefs();
    render();
  });

  if (unitFilterSelect) {
    unitFilterSelect.addEventListener("change", function () {
      state.unit = unitFilterSelect.value;
      state.page = 1;
      savePrefs();
      render();
    });
  }

  sortSelect.addEventListener("change", function () {
    state.sort = sortSelect.value;
    savePrefs();
    render();
  });

  pageSizeSelect.addEventListener("change", function () {
    state.pageSize = pageSizeSelect.value;
    state.page = 1;
    savePrefs();
    render();
  });

  colToggles.forEach(function (input) {
    input.addEventListener("change", function () {
      var col = input.getAttribute("data-col-toggle");
      state.columns[col] = input.checked;
      savePrefs();
      applyColumnVisibility();
    });
  });

  loadPrefs();
  render();
})();
