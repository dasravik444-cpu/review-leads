/* QR landing page behaviour. No cookies, no storage, no tracking: the page only remembers, while it is open,
   that the guest went to write a review, so that when they come back it shows the payment button as the
   next step. Google's review page cannot send guests back by itself (it has no "return to" address). */
(function () {
  "use strict";
  var root = document.documentElement;
  var review = document.getElementById("review");
  var pay = document.getElementById("pay");
  var reviewOpened = false;

  function returned() {
    if (reviewOpened) {
      root.classList.add("returned");
      if (pay && typeof pay.focus === "function") {
        try { pay.focus({ preventScroll: false }); } catch (e) { pay.focus(); }
      }
    }
  }

  if (review) {
    review.addEventListener("click", function () {
      reviewOpened = true;
      root.classList.add("review-opened");
    });
  }
  // The guest switches back from the Google Maps app or the review tab to this page.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") { returned(); }
  });
  window.addEventListener("focus", returned);
  // Coming back with the browser's Back button restores this page from memory.
  window.addEventListener("pageshow", function (e) { if (e.persisted) { returned(); } });
})();
