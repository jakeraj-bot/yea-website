(function () {
  const programInputs = document.querySelectorAll('input[name="program"]');
  const locationSelect = document.querySelector('select[name="program_location"]');
  const modal = document.getElementById("dale-ave-bus-modal");
  if (!programInputs.length || !locationSelect) return;

  const afterSchoolLocations = ["school_18", "school_26", "dale_ave"];
  const summerLocations = ["caldwell"];
  let lastLocation = locationSelect.value;
  let scrollY = 0;

  function selectedProgram() {
    const checked = document.querySelector('input[name="program"]:checked');
    return checked ? checked.value : "";
  }

  function updateLocationOptions() {
    const program = selectedProgram();
    const allowed = program === "summer_camp" ? summerLocations : afterSchoolLocations;
    Array.from(locationSelect.options).forEach((option) => {
      if (!option.value) return;
      option.hidden = !allowed.includes(option.value);
      option.disabled = !allowed.includes(option.value);
    });
    if (!allowed.includes(locationSelect.value)) {
      locationSelect.value = allowed[0];
    }
    lastLocation = locationSelect.value;
  }

  function lockScroll() {
    scrollY = window.scrollY || document.documentElement.scrollTop || 0;
    document.body.classList.add("modal-open");
    document.body.style.top = `-${scrollY}px`;
  }

  function unlockScroll() {
    document.body.classList.remove("modal-open");
    document.body.style.top = "";
    window.scrollTo(0, scrollY);
  }

  function showDaleAveModal() {
    if (!modal) return;
    modal.hidden = false;
    lockScroll();
    const closeBtn = modal.querySelector("[data-modal-close]");
    if (closeBtn) closeBtn.focus();
  }

  function hideDaleAveModal() {
    if (!modal) return;
    modal.hidden = true;
    unlockScroll();
  }

  function handleLocationChange() {
    const value = locationSelect.value;
    if (value === "dale_ave" && lastLocation !== "dale_ave") {
      showDaleAveModal();
    }
    lastLocation = value;
  }

  programInputs.forEach((input) => input.addEventListener("change", updateLocationOptions));
  locationSelect.addEventListener("change", handleLocationChange);

  if (modal) {
    modal.addEventListener("click", (event) => {
      if (event.target.matches("[data-modal-close], .modal-backdrop")) {
        hideDaleAveModal();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) hideDaleAveModal();
    });
  }

  updateLocationOptions();
})();
