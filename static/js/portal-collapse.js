(function () {
  var body = document.body;
  if (!body || !/portal-area-staff|portal-area-admin/.test(body.className)) return;

  var STORAGE_KEY = "yea-portal-collapse";
  var pageKey = window.location.pathname;

  function loadState() {
    try {
      return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (err) {
      return {};
    }
  }

  function saveState(state) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  var stored = loadState();
  var pageState = stored[pageKey] || {};

  function sectionKey(heading) {
    return (heading.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function applyCollapsed(section, collapsed) {
    section.classList.toggle("is-collapsed", collapsed);
    var toggle = section.querySelector(".portal-collapse-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  function persist(section, collapsed) {
    var toggle = section.querySelector(".portal-collapse-toggle");
    if (!toggle) return;
    pageState[sectionKey(toggle)] = collapsed;
    stored[pageKey] = pageState;
    saveState(stored);
  }

  function enhanceCard(card) {
    if (
      card.classList.contains("portal-collapse") ||
      card.classList.contains("portal-panel") ||
      card.classList.contains("portal-callout") ||
      card.classList.contains("portal-balance-banner") ||
      card.classList.contains("portal-collapse-skip") ||
      card.hidden
    ) {
      return;
    }
    var heading = card.querySelector(":scope > h2, :scope > h3");
    if (!heading) return;
    var key = sectionKey(heading);
    var collapsed = Object.prototype.hasOwnProperty.call(pageState, key) ? pageState[key] : true;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "portal-collapse-toggle";
    button.textContent = heading.textContent;
    var bodyWrap = document.createElement("div");
    bodyWrap.className = "portal-collapse-body";
    var next = heading.nextSibling;
    while (next) {
      var current = next;
      next = current.nextSibling;
      bodyWrap.appendChild(current);
    }
    heading.replaceWith(button);
    card.appendChild(bodyWrap);
    card.classList.add("portal-collapse");
    applyCollapsed(card, collapsed);
    button.addEventListener("click", function () {
      var nowCollapsed = !card.classList.contains("is-collapsed");
      applyCollapsed(card, nowCollapsed);
      persist(card, nowCollapsed);
    });
  }

  function wrapHeadingBlock(heading) {
    if (heading.closest(".card, .portal-collapse, .portal-family-tabs, nav")) return;
    var parent = heading.parentNode;
    if (!parent) return;
    var section = document.createElement("section");
    section.className = "portal-collapse";
    parent.insertBefore(section, heading);
    var button = document.createElement("button");
    button.type = "button";
    button.className = "portal-collapse-toggle";
    button.textContent = heading.textContent;
    var bodyWrap = document.createElement("div");
    bodyWrap.className = "portal-collapse-body";
    section.appendChild(button);
    var sibling = heading.nextSibling;
    heading.remove();
    while (sibling && !(sibling.nodeType === 1 && (sibling.matches("h2") || sibling.classList.contains("portal-collapse")))) {
      var current = sibling;
      sibling = current.nextSibling;
      bodyWrap.appendChild(current);
    }
    section.appendChild(bodyWrap);
    var key = sectionKey(button);
    var collapsed = Object.prototype.hasOwnProperty.call(pageState, key) ? pageState[key] : true;
    applyCollapsed(section, collapsed);
    button.addEventListener("click", function () {
      var nowCollapsed = !section.classList.contains("is-collapsed");
      applyCollapsed(section, nowCollapsed);
      persist(section, nowCollapsed);
    });
  }

  var content = document.querySelector(".page-content");
  if (!content) return;

  content.querySelectorAll(".card").forEach(enhanceCard);
  Array.from(content.querySelectorAll(".container > h2")).forEach(wrapHeadingBlock);

  var sections = content.querySelectorAll(".portal-collapse");
  if (!sections.length) return;

  var container = content.querySelector(".container") || content;
  var bar = document.createElement("div");
  bar.className = "portal-collapse-bar portal-no-print";
  bar.innerHTML =
    '<button type="button" class="btn btn-secondary btn-sm" data-collapse-all="open">Expand all</button>' +
    '<button type="button" class="btn btn-secondary btn-sm" data-collapse-all="close">Collapse all</button>';
  container.insertBefore(bar, container.firstChild);
  bar.addEventListener("click", function (event) {
    var button = event.target.closest("[data-collapse-all]");
    if (!button) return;
    var collapseAll = button.getAttribute("data-collapse-all") === "close";
    content.querySelectorAll(".portal-collapse").forEach(function (section) {
      applyCollapsed(section, collapseAll);
      persist(section, collapseAll);
    });
  });
})();
