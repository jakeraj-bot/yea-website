document.querySelectorAll(".giving-form").forEach((form) => {
  const customRadio = form.querySelector('.amount-button--custom input[value="custom"]');
  const customField = form.querySelector(".giving-custom-amount");
  const customInput = customField?.querySelector('input[name="custom_amount"]');

  if (!customRadio || !customField) return;

  form.querySelectorAll('input[name="amount"]').forEach((input) => {
    input.addEventListener("change", () => {
      const isCustom = input.value === "custom";
      customField.hidden = !isCustom;
      if (isCustom) {
        customInput.required = true;
        customInput.focus();
      } else {
        customInput.required = false;
        customInput.value = "";
      }
    });
  });
});
