(function () {
  function fileListFrom(files) {
    var transfer = new DataTransfer();
    Array.prototype.forEach.call(files, function (file) {
      transfer.items.add(file);
    });
    return transfer.files;
  }

  function renderAttachmentList(input) {
    var wrap = input.closest(".portal-email-upload");
    if (!wrap) return;
    var ul = wrap.querySelector("[data-attachment-list]");
    if (!ul) return;
    ul.innerHTML = "";
    var files = Array.prototype.slice.call(input.files || []);
    if (!files.length) {
      ul.hidden = true;
      return;
    }
    ul.hidden = false;
    files.forEach(function (file, index) {
      var item = document.createElement("li");
      item.className = "portal-email-attachment-item";
      var name = document.createElement("span");
      name.textContent = file.name;
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-secondary btn-sm";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () {
        var next = files.filter(function (_file, i) {
          return i !== index;
        });
        input.files = fileListFrom(next);
        renderAttachmentList(input);
      });
      item.appendChild(name);
      item.appendChild(remove);
      ul.appendChild(item);
    });
  }

  document.querySelectorAll("[data-email-attachments]").forEach(function (input) {
    input.addEventListener("change", function () {
      renderAttachmentList(input);
    });
    renderAttachmentList(input);
  });

  function setOpen(item, open) {
    var toggle = item.querySelector("[data-email-ledger-toggle]");
    var detail = item.querySelector("[data-email-ledger-detail]");
    if (!toggle || !detail) return;
    item.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    detail.hidden = !open;
  }

  document.querySelectorAll("[data-email-ledger-item]").forEach(function (item) {
    var toggle = item.querySelector("[data-email-ledger-toggle]");
    var closer = item.querySelector("[data-email-ledger-close]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        setOpen(item, !item.classList.contains("is-open"));
      });
    }
    if (closer) {
      closer.addEventListener("click", function () {
        setOpen(item, false);
      });
    }
  });
})();
