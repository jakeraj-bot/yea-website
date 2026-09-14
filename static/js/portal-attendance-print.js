(function () {
  var pageClones = [];

  function restoreAttendancePrintTables() {
    for (var i = 0; i < pageClones.length; i++) {
      var node = pageClones[i];
      if (node && node.parentNode) node.parentNode.removeChild(node);
    }
    pageClones = [];
    var sources = document.querySelectorAll(".portal-attendance-print-table[data-print-source]");
    for (var s = 0; s < sources.length; s++) sources[s].removeAttribute("data-print-source");
  }

  function paginateAttendancePrintTables() {
    restoreAttendancePrintTables();
    var tables = document.querySelectorAll(".portal-attendance-print-table");
    for (var t = 0; t < tables.length; t++) {
      var table = tables[t];
      if (table.classList.contains("portal-attendance-print-page")) continue;
      var thead = table.tHead;
      var tbody = table.tBodies[0];
      if (!thead || !tbody) continue;
      var rows = Array.prototype.slice.call(tbody.rows);
      if (!rows.length) continue;
      var chunk = parseInt(table.getAttribute("data-print-row-chunk") || "8", 10);
      if (!chunk || chunk < 1) chunk = 8;
      var host = table.parentNode;
      for (var i = 0; i < rows.length; i += chunk) {
        var clone = table.cloneNode(false);
        clone.className = table.className + " portal-attendance-print-page";
        clone.removeAttribute("id");
        clone.appendChild(thead.cloneNode(true));
        var body = document.createElement("tbody");
        var slice = rows.slice(i, i + chunk);
        for (var r = 0; r < slice.length; r++) body.appendChild(slice[r].cloneNode(true));
        clone.appendChild(body);
        host.insertBefore(clone, table);
        pageClones.push(clone);
      }
      table.setAttribute("data-print-source", "1");
    }
  }

  window.portalPaginateAttendanceTables = paginateAttendancePrintTables;
  window.portalRestoreAttendanceTables = restoreAttendancePrintTables;

  document.addEventListener("beforeprint", paginateAttendancePrintTables);
  document.addEventListener("afterprint", restoreAttendancePrintTables);
})();
