(function () {
  const programInputs = document.querySelectorAll('input[name="programs"]');
  const locationSelect = document.querySelector('select[name="program_location"]');
  const modal = document.getElementById("dale-ave-bus-modal");
  if (!programInputs.length || !locationSelect) return;

  const rulesEl = document.getElementById("program-location-rules");
  let locationRules = {};
  if (rulesEl && rulesEl.textContent) {
    try {
      locationRules = JSON.parse(rulesEl.textContent);
    } catch (error) {
      locationRules = {};
    }
  }

  let lastLocation = locationSelect.value;
  let scrollY = 0;

  function selectedPrograms() {
    return Array.from(document.querySelectorAll('input[name="programs"]:checked')).map(function (input) {
      return input.value;
    });
  }

  function allowedLocations(programs) {
    if (!programs.length) return [];
    var allowed = null;
    programs.forEach(function (program) {
      var keys = locationRules[program] && locationRules[program].length ? locationRules[program].slice() : [];
      if (program === "summer_camp" && !keys.length) keys = ["caldwell"];
      if (program === "before_care" && !keys.length) keys = ["school_18", "school_26"];
      if (program === "after_school" && !keys.length) keys = ["school_18", "school_26", "dale_ave"];
      if (allowed === null) {
        allowed = keys;
      } else {
        allowed = allowed.filter(function (key) {
          return keys.indexOf(key) !== -1;
        });
      }
    });
    return allowed || [];
  }

  function enforceSummerCampExclusive(changedInput) {
    if (!changedInput || changedInput.value !== "summer_camp" || !changedInput.checked) return;
    programInputs.forEach(function (input) {
      if (input.value !== "summer_camp") input.checked = false;
    });
  }

  function enforceNonSummerExclusive(changedInput) {
    if (!changedInput || changedInput.value === "summer_camp" || !changedInput.checked) return;
    programInputs.forEach(function (input) {
      if (input.value === "summer_camp") input.checked = false;
    });
  }

  function updateLocationOptions() {
    const programs = selectedPrograms();
    const allowed = allowedLocations(programs);
    Array.from(locationSelect.options).forEach(function (option) {
      if (!option.value) return;
      option.hidden = allowed.length > 0 && allowed.indexOf(option.value) === -1;
      option.disabled = allowed.length > 0 && allowed.indexOf(option.value) === -1;
    });
    if (allowed.length && allowed.indexOf(locationSelect.value) === -1) {
      locationSelect.value = allowed[0] || "";
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

  programInputs.forEach(function (input) {
    input.addEventListener("change", function (event) {
      enforceSummerCampExclusive(event.target);
      enforceNonSummerExclusive(event.target);
      updateLocationOptions();
    });
  });
  locationSelect.addEventListener("change", handleLocationChange);

  if (modal) {
    modal.addEventListener("click", function (event) {
      if (event.target.matches("[data-modal-close], .modal-backdrop")) {
        hideDaleAveModal();
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !modal.hidden) hideDaleAveModal();
    });
  }

  updateLocationOptions();
})();
