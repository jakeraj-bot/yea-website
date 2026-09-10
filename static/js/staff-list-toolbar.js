(function () {
  document.querySelectorAll("[data-staff-list-toolbar]").forEach(function (toolbar) {
    var table = toolbar.parentElement && toolbar.parentElement.querySelector("table");
    if (!table || !table.tBodies.length) return;
    var tbody = table.tBodies[0];
    var search = toolbar.querySelector(".portal-list-search");
    var filter = toolbar.querySelector(".portal-list-filter");
    var sort = toolbar.querySelector(".portal-list-sort");

    function rows() {
      return Array.prototype.slice.call(tbody.rows);
    }

    function submittedValue(row) {
      return row.getAttribute("data-submitted") || "";
    }

    function apply() {
      var q = (search && search.value || "").trim().toLowerCase();
      var f = (filter && filter.value || "All").trim().toLowerCase();
      var mode = (sort && sort.value || "").toLowerCase();
      var visible = rows();
      visible.forEach(function (row) {
        var text = row.textContent.toLowerCase();
        var show = (!q || text.indexOf(q) !== -1) && (f === "all" || text.indexOf(f) !== -1);
        row.hidden = !show;
      });
      if (mode.indexOf("oldest") !== -1 || mode.indexOf("newest") !== -1) {
        visible.sort(function (a, b) {
          var av = submittedValue(a);
          var bv = submittedValue(b);
          if (av < bv) return mode.indexOf("newest") !== -1 ? 1 : -1;
          if (av > bv) return mode.indexOf("newest") !== -1 ? -1 : 1;
          return 0;
        });
        visible.forEach(function (row) {
          tbody.appendChild(row);
        });
      }
    }

    if (search) search.addEventListener("input", apply);
    if (filter) filter.addEventListener("change", apply);
    if (sort) sort.addEventListener("change", apply);
  });
})();
