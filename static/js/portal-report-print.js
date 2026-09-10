(function () {
  function headerColspan(thead) {
    var first = thead.querySelector("tr");
    if (!first) return 1;
    var span = 0;
    var cells = first.querySelectorAll("th, td");
    for (var i = 0; i < cells.length; i++) {
      span += parseInt(cells[i].getAttribute("colspan") || "1", 10) || 1;
    }
    return Math.max(span, 1);
  }

  function clonePrintHeader(header) {
    var clone = header.cloneNode(true);
    clone.classList.add("portal-print-running-header");
    clone.classList.remove("portal-no-print");
    var logo = clone.querySelector(".portal-medical-report-logo");
    if (logo) logo.classList.add("portal-print-running-logo");
    return clone;
  }

  function makeTitleRow(header, colspan) {
    var row = document.createElement("tr");
    row.className = "portal-print-title-row";
    var th = document.createElement("th");
    th.setAttribute("colspan", String(colspan || 1));
    th.setAttribute("scope", "colgroup");
    th.appendChild(clonePrintHeader(header));
    row.appendChild(th);
    return row;
  }

  function wrapSheetWithoutTables(sheet, header) {
    var frame = document.createElement("table");
    frame.className = "portal-report-print-frame";
    frame.setAttribute("role", "presentation");
    var thead = document.createElement("thead");
    thead.appendChild(makeTitleRow(header, 1));
    frame.appendChild(thead);
    var tbody = document.createElement("tbody");
    var bodyRow = document.createElement("tr");
    var bodyCell = document.createElement("td");
    bodyCell.className = "portal-report-print-body";
    var move = [];
    for (var i = 0; i < sheet.childNodes.length; i++) {
      if (sheet.childNodes[i] !== header) move.push(sheet.childNodes[i]);
    }
    for (var j = 0; j < move.length; j++) bodyCell.appendChild(move[j]);
    bodyRow.appendChild(bodyCell);
    tbody.appendChild(bodyRow);
    frame.appendChild(tbody);
    sheet.appendChild(frame);
  }

  function wrapReportSheetsForPrint() {
    var sheets = document.querySelectorAll(".portal-medical-report-sheet");
    for (var s = 0; s < sheets.length; s++) {
      var sheet = sheets[s];
      if (sheet.classList.contains("portal-attendance-print-sheet")) continue;
      if (sheet.querySelector(".portal-print-title-row")) continue;
      var header = sheet.querySelector(".portal-medical-report-header");
      if (!header) continue;

      var tables = sheet.querySelectorAll("table");
      var injected = 0;
      for (var t = 0; t < tables.length; t++) {
        var table = tables[t];
        if (table.classList.contains("portal-report-print-frame")) continue;
        var thead = table.tHead || table.querySelector("thead");
        if (!thead) continue;
        thead.insertBefore(makeTitleRow(header, headerColspan(thead)), thead.firstChild);
        injected += 1;
      }
      if (!injected) wrapSheetWithoutTables(sheet, header);
    }
  }

  function stampPrintDate() {
    var style = document.getElementById("report-print-page-style");
    if (!style) return;
    var stamp = new Date().toLocaleString();
    style.textContent = style.textContent.replace(
      /content: "Printed [^"]*";/,
      'content: "Printed ' + stamp.replace(/"/g, "") + '";'
    );
  }

  window.portalWrapReportSheetsForPrint = wrapReportSheetsForPrint;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapReportSheetsForPrint);
  } else {
    wrapReportSheetsForPrint();
  }
  document.addEventListener("beforeprint", stampPrintDate);
})();
