(function () {
  document.querySelectorAll("[data-staff-list-toolbar]").forEach(function (toolbar) {
    var table = toolbar.parentElement && toolbar.parentElement.querySelector("table");
    if (!table || !table.tBodies.length) return;
    var tbody = table.tBodies[0];
    var search = toolbar.querySelector(".portal-list-search");
    var filter = toolbar.querySelector(".portal-list-filter");

    function rows() {
      return Array.prototype.slice.call(tbody.rows);
    }

    function apply() {
      var q = (search && search.value || "").trim().toLowerCase();
      var f = (filter && filter.value || "All").trim().toLowerCase();
      rows().forEach(function (row) {
        var text = row.textContent.toLowerCase();
        var show = (!q || text.indexOf(q) !== -1) && (f === "all" || text.indexOf(f) !== -1);
        row.hidden = !show;
      });
    }

    if (search) search.addEventListener("input", apply);
    if (filter) filter.addEventListener("change", apply);
  });
})();
