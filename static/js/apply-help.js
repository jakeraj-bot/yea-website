(function () {
  var INTERVAL_MS = 7000;

  function initApplyHelp() {
    var modal = document.getElementById("apply-help-modal");
    if (!modal) return;

    var slides = Array.prototype.slice.call(modal.querySelectorAll("[data-help-slide]"));
    var status = modal.querySelector("[data-help-status]");
    var playBtn = modal.querySelector("[data-help-play]");
    var prevBtn = modal.querySelector("[data-help-prev]");
    var nextBtn = modal.querySelector("[data-help-next]");
    var index = 0;
    var timer = null;
    var playing = true;
    var statusTemplate = (status && status.getAttribute("data-template")) || "";

    function show(i) {
      index = (i + slides.length) % slides.length;
      slides.forEach(function (slide, n) {
        slide.hidden = n !== index;
        slide.classList.toggle("is-active", n === index);
      });
      if (status && statusTemplate) {
        status.textContent = statusTemplate.replace("{current}", String(index + 1)).replace("{total}", String(slides.length));
      }
      if (prevBtn) prevBtn.disabled = index <= 0;
      if (nextBtn) nextBtn.disabled = index >= slides.length - 1;
    }

    function stop() {
      playing = false;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (playBtn) playBtn.textContent = playBtn.getAttribute("data-play-label") || "Play";
    }

    function start() {
      playing = true;
      if (timer) clearInterval(timer);
      timer = setInterval(function () {
        if (index >= slides.length - 1) {
          stop();
          return;
        }
        show(index + 1);
      }, INTERVAL_MS);
      if (playBtn) playBtn.textContent = playBtn.getAttribute("data-pause-label") || "Pause";
    }

    function open() {
      modal.hidden = false;
      document.body.classList.add("modal-open");
      show(0);
      start();
      var closeBtn = modal.querySelector("[data-help-close]");
      if (closeBtn) closeBtn.focus();
    }

    function close() {
      stop();
      modal.hidden = true;
      document.body.classList.remove("modal-open");
    }

    document.querySelectorAll("[data-open-apply-help]").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        open();
      });
    });

    modal.querySelectorAll("[data-help-close]").forEach(function (btn) {
      btn.addEventListener("click", close);
    });
    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        stop();
        show(index - 1);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        stop();
        show(index + 1);
      });
    }
    if (playBtn) {
      playBtn.addEventListener("click", function () {
        if (playing) stop();
        else start();
      });
    }

    document.addEventListener("keydown", function (event) {
      if (modal.hidden) return;
      if (event.key === "Escape") close();
    });

    if (window.location.hash === "#how-to-apply" || /(?:\?|&)help=1(?:&|$)/.test(window.location.search)) {
      open();
    }
  }

  window.initApplyHelp = initApplyHelp;
})();
