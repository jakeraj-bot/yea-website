(function () {
  var STORAGE_KEY = "yea-parent-a2hs-dismissed";
  var banner = document.getElementById("yea-a2hs");
  var more = document.getElementById("parent-more");

  function isStandalone() {
    return (
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true
    );
  }

  function isPhone() {
    if (window.matchMedia && window.matchMedia("(max-width: 720px)").matches) return true;
    return Boolean(window.matchMedia && window.matchMedia("(pointer: coarse) and (max-width: 900px)").matches);
  }

  function isiOS() {
    return /iPhone|iPad|iPod/i.test(window.navigator.userAgent || "");
  }

  if (isStandalone()) {
    document.documentElement.classList.add("yea-parent-standalone");
  }

  if (banner) {
    var dismissed = false;
    try {
      dismissed = window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (err) {
      dismissed = false;
    }
    var deferredPrompt = null;
    var iosHint = banner.querySelector("[data-a2hs-ios]");
    var androidHint = banner.querySelector("[data-a2hs-android]");
    var installBtn = banner.querySelector("[data-a2hs-install]");
    if (iosHint && androidHint) {
      if (isiOS()) {
        androidHint.hidden = true;
      } else {
        iosHint.hidden = true;
      }
    }
    function showBanner() {
      if (dismissed || isStandalone() || !isPhone()) return;
      banner.hidden = false;
    }
    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferredPrompt = event;
      if (installBtn) installBtn.hidden = false;
      showBanner();
    });
    showBanner();
    banner.querySelectorAll("[data-a2hs-dismiss]").forEach(function (button) {
      button.addEventListener("click", function () {
        banner.hidden = true;
        dismissed = true;
        try {
          window.localStorage.setItem(STORAGE_KEY, "1");
        } catch (err) {}
      });
    });
    if (installBtn) {
      installBtn.addEventListener("click", function () {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
          deferredPrompt = null;
          banner.hidden = true;
          try {
            window.localStorage.setItem(STORAGE_KEY, "1");
          } catch (err) {}
        });
      });
    }
  }

  function closeMore() {
    if (!more) return;
    more.hidden = true;
    document.body.classList.remove("is-parent-more-open");
    document.querySelectorAll("[data-parent-more]").forEach(function (button) {
      button.setAttribute("aria-expanded", "false");
    });
  }

  function openMore() {
    if (!more) return;
    more.hidden = false;
    document.body.classList.add("is-parent-more-open");
    document.querySelectorAll("[data-parent-more]").forEach(function (button) {
      button.setAttribute("aria-expanded", "true");
    });
  }

  document.querySelectorAll("[data-parent-more]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!more) return;
      if (more.hidden) openMore();
      else closeMore();
    });
  });
  document.querySelectorAll("[data-parent-more-close]").forEach(function (node) {
    node.addEventListener("click", closeMore);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMore();
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/portal/parent/sw.js", { scope: "/portal/" }).catch(function () {});
  }
})();
