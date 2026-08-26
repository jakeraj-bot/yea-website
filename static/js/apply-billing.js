(function () {
  var paymentSelect = document.querySelector('select[name="payment_method"]');
  var fourCsBlock = document.getElementById("apply-fourcs-block");
  var otherInput = document.querySelector('[name="payment_method_other"]');
  var otherGroup = otherInput ? otherInput.closest(".form-group") : null;
  if (!paymentSelect) return;

  function togglePaymentExtras() {
    var isFourCs = paymentSelect.value === "4cs";
    var isOther = paymentSelect.value === "other";
    if (fourCsBlock) {
      fourCsBlock.hidden = !isFourCs;
      fourCsBlock.querySelectorAll("input, select, textarea").forEach(function (input) {
        input.disabled = !isFourCs;
      });
    }
    if (otherGroup) {
      otherGroup.hidden = !isOther;
    }
    if (otherInput) {
      otherInput.required = isOther;
      if (!isOther) {
        otherInput.setCustomValidity("");
      }
    }
  }

  paymentSelect.addEventListener("change", togglePaymentExtras);
  togglePaymentExtras();
})();
