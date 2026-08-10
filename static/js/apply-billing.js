(function () {
  var paymentSelect = document.querySelector('select[name="payment_method"]');
  var fourCsBlock = document.getElementById("apply-fourcs-block");
  if (!paymentSelect || !fourCsBlock) return;

  function toggleFourCsBlock() {
    var isFourCs = paymentSelect.value === "4cs";
    fourCsBlock.hidden = !isFourCs;
    fourCsBlock.querySelectorAll("input, select, textarea").forEach(function (input) {
      input.disabled = !isFourCs;
    });
  }

  paymentSelect.addEventListener("change", toggleFourCsBlock);
  toggleFourCsBlock();
})();
