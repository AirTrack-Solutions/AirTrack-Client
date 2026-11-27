/* A7 (Trevor 6924 / Bob 6925): one accessible tooltip for compact Departure/Arrival names on the Aircraft table.
   The cell never changes size: the tooltip is position:fixed, appended to <body>, outside the table's layout flow.
   Shown on hover and on keyboard focus of td.ac-airport when the name is truncated; hidden on leave/blur, on Escape,
   and when the cell scrolls out of view (it follows the cell while visible). Delegated listeners, so rows re-rendered by search keep working. */
(function () {
  "use strict";
  var SEL = "td.ac-airport, td.ac-airline";  // A8: Airline cells share the same single tooltip
  var NAME = ".ac-airport-name, .ac-airline-name";
  var tip = null, owner = null, dismissed = null;

  function ensureTip() {
    if (tip) return tip;
    tip = document.createElement("div");
    tip.id = "ac-airport-tip";
    tip.className = "ac-airport-tip";
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    tip.addEventListener("mouseleave", function (e) {
      if (owner && !(e.relatedTarget && owner.contains(e.relatedTarget)) && owner !== document.activeElement) hide();
    });
    document.body.appendChild(tip);
    return tip;
  }
  function nameOf(cell) {
    var s = cell.querySelector(NAME);
    return s ? s.textContent.replace(/\s+/g, " ").trim() : "";
  }
  function truncated(cell) {
    var s = cell.querySelector(NAME);
    return !!s && s.scrollWidth > s.clientWidth + 1;
  }
  function place(cell) {
    var r = cell.getBoundingClientRect(), t = tip, gap = 4, vw = document.documentElement.clientWidth, vh = window.innerHeight;
    t.style.left = "0px"; t.style.top = "0px";
    var w = t.offsetWidth, h = t.offsetHeight;
    var left = Math.min(Math.max(4, r.left), Math.max(4, vw - w - 4));
    var top = r.bottom + gap;
    if (top + h > vh - 4) top = Math.max(4, r.top - gap - h);
    t.style.left = Math.round(left) + "px"; t.style.top = Math.round(top) + "px";
  }
  function show(cell) {
    if (dismissed === cell) return;
    if (!truncated(cell)) { if (owner === cell) hide(); return; }
    ensureTip();
    if (owner && owner !== cell) owner.removeAttribute("aria-describedby");
    owner = cell;
    tip.textContent = nameOf(cell);
    tip.hidden = false;
    cell.setAttribute("aria-describedby", tip.id);
    place(cell);
  }
  function hide() {
    if (tip) tip.hidden = true;
    if (owner) owner.removeAttribute("aria-describedby");
    owner = null;
  }

  document.addEventListener("mouseover", function (e) {
    var c = e.target.closest && e.target.closest(SEL);
    if (c && c !== owner) { dismissed = null; show(c); }
  });
  document.addEventListener("mouseout", function (e) {
    var c = e.target.closest && e.target.closest(SEL);
    if (!c || c !== owner) return;
    var to = e.relatedTarget;
    if (to && (c.contains(to) || (tip && tip.contains(to)))) return;
    if (document.activeElement !== c) hide();
  });
  document.addEventListener("focusin", function (e) {
    var c = e.target.closest && e.target.closest(SEL);
    if (c) { dismissed = null; show(c); } else if (owner) hide();
  });
  document.addEventListener("focusout", function (e) {
    var c = e.target.closest && e.target.closest(SEL);
    if (c && c === owner) hide();
  });
  document.addEventListener("keydown", function (e) {
    if ((e.key === "Escape" || e.key === "Esc") && owner) { dismissed = owner; hide(); }
  });
  // the tooltip is fixed-position: on page or table-region scroll (including the browser scrolling a newly focused
  // cell into view) follow the cell, and hide only once the cell has left the viewport
  function follow() {
    if (!owner) return;
    var r = owner.getBoundingClientRect();
    var w = owner.closest(".aircraft-table-wrapper"), b = w ? w.getBoundingClientRect() : null;
    var gone = r.bottom <= 0 || r.top >= window.innerHeight || r.right <= 0 || r.left >= document.documentElement.clientWidth;
    if (b) gone = gone || r.right <= b.left || r.left >= b.left + w.clientLeft + w.clientWidth;  // scrolled out of the table region sideways
    if (gone) hide();
    else place(owner);
  }
  document.addEventListener("scroll", follow, true);
  window.addEventListener("resize", follow);
})();
