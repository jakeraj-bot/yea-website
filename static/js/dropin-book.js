(function () {
  const programSelect = document.querySelector('select[name="program"]');
  const locationSelect = document.querySelector('select[name="location"]');
  if (!programSelect || !locationSelect) return;

  const afterSchool = ["school_18", "school_26", "dale_ave"];
  const summerCamp = ["caldwell"];

  function updateLocations() {
    const allowed = programSelect.value === "summer_camp" ? summerCamp : afterSchool;
    Array.from(locationSelect.options).forEach((option) => {
      if (!option.value) return;
      const show = allowed.includes(option.value);
      option.hidden = !show;
      option.disabled = !show;
    });
    if (!allowed.includes(locationSelect.value)) {
      locationSelect.value = allowed[0];
    }
  }

  programSelect.addEventListener("change", updateLocations);
  updateLocations();
})();
