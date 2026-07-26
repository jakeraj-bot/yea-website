document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".site-nav");
  const dropdownItems = document.querySelectorAll(".has-dropdown");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open);
    });
  }

  const closeDropdowns = () => {
    dropdownItems.forEach((item) => {
      item.classList.remove("is-open");
      const link = item.querySelector(":scope > a");
      if (link) {
        link.setAttribute("aria-expanded", "false");
      }
    });
  };

  dropdownItems.forEach((item) => {
    const link = item.querySelector(":scope > a");
    if (!link) return;

    link.setAttribute("aria-haspopup", "true");
    link.setAttribute("aria-expanded", "false");

    link.addEventListener("click", (event) => {
      event.preventDefault();
      const isOpen = item.classList.contains("is-open");
      closeDropdowns();

      if (!isOpen) {
        item.classList.add("is-open");
        link.setAttribute("aria-expanded", "true");
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".has-dropdown")) {
      closeDropdowns();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDropdowns();
    }
  });
});
