(function () {
  var form = document.querySelector("[data-family-search]");
  if (!form) return;

  var input = form.querySelector('input[name="q"]');
  var list = form.querySelector(".portal-family-account-search-results");
  if (!input || !list) return;

  var timer = null;
  var lastQuery = "";

  function hideList() {
    list.hidden = true;
    list.innerHTML = "";
  }

  function showResults(results) {
    list.innerHTML = "";
    if (!results.length) {
      var empty = document.createElement("p");
      empty.className = "form-note portal-family-account-search-empty";
      empty.textContent = "No matching children.";
      list.appendChild(empty);
      list.hidden = false;
      return;
    }
    results.forEach(function (row) {
      var link = document.createElement("a");
      link.className = "portal-family-search-hit";
      link.href = row.url;
      link.setAttribute("role", "option");
      var title = document.createElement("strong");
      title.textContent = row.child_name || row.family_name || "Family account";
      link.appendChild(title);
      if (row.child_name && row.family_name) {
        var family = document.createElement("span");
        family.textContent = row.family_name;
        link.appendChild(family);
      }
      if (row.unit) {
        var unit = document.createElement("span");
        unit.textContent = row.unit;
        link.appendChild(unit);
      }
      list.appendChild(link);
    });
    list.hidden = false;
  }

  function fetchResults(query) {
    if (!query) {
      hideList();
      return;
    }
    if (query === lastQuery) return;
    lastQuery = query;
    var url = form.action + (form.action.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(query) + "&format=json";
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error("search failed");
        return response.json();
      })
      .then(function (data) {
        if (input.value.trim() !== query) return;
        showResults(data.results || []);
      })
      .catch(function () {
        hideList();
      });
  }

  input.addEventListener("input", function () {
    var query = input.value.trim();
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      fetchResults(query);
    }, 180);
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Escape") hideList();
  });

  document.addEventListener("click", function (event) {
    if (!form.contains(event.target)) hideList();
  });
})();
