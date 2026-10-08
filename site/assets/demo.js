/* Preview page for prospects (the link in our letters): shows how their own page would look.
   The business name comes from the address (?n=...) and is only ever written as text, never as HTML. */
(function () {
  "use strict";
  var params = new URLSearchParams(window.location.search);
  // Links in English e-mails carry lang=en, German letters lang=de: switch when this page is in the other language.
  var lang = params.get("lang");
  if ((lang === "en" || lang === "de") && document.documentElement.lang !== lang) {
    window.location.replace(lang + ".html" + window.location.search);
    return;
  }
  var name = (params.get("n") || "").trim().slice(0, 80);
  if (!name) { return; }
  var nodes = document.querySelectorAll("[data-business]");
  for (var i = 0; i < nodes.length; i++) { nodes[i].textContent = name; }
  document.title = document.title.replace(/^[^|]*/, name + " ");
  var wa = document.getElementById("whatsapp");
  if (wa && wa.getAttribute("data-template")) {
    var text = wa.getAttribute("data-template").replace("{business}", name);
    var base = wa.getAttribute("href").split("?")[0];
    wa.setAttribute("href", base + "?text=" + encodeURIComponent(text));
  }
})();
