// Resolves ICAO/IATA to readable names on your edit screen.

(function () {
  "use strict";

  const cache = new Map(); // code -> airport object or null

  async function lookup(code) {
    const key = (code || "").trim().toUpperCase();
    if (!key) return null;
    if (cache.has(key)) return cache.get(key);

    try {
      const r = await fetch(`/api/airports/lookup?code=${encodeURIComponent(key)}`, { credentials: "same-origin" });
      const j = await r.json();
      const val = (j && j.ok && j.found) ? j.airport : null;
      cache.set(key, val);
      return val;
    } catch {
      return null;
    }
  }

  function setReadable(targetId, text) {
    const el = document.getElementById(targetId);
    if (el) el.textContent = text || "";
  }

  async function resolveInto(inputId, targetId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const code = input.value.trim();
    if (!code) {
      setReadable(targetId, "");
      return;
    }
    const info = await lookup(code);
    setReadable(targetId, info ? info.display : `Unknown code: ${code}`);
  }

  function bind(inputId, targetId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const doResolve = () => resolveInto(inputId, targetId);
    input.addEventListener("blur", doResolve);
    input.addEventListener("change", doResolve);
    input.addEventListener("keyup", (e) => {
      if (e.key === "Enter") doResolve();
    });
  }

  async function initAirportResolver() {
    bind("dep_icao", "dep_airport_readable");
    bind("arr_icao", "arr_airport_readable");
    await resolveInto("dep_icao", "dep_airport_readable");
    await resolveInto("arr_icao", "arr_airport_readable");
  }

  window.AirTrackAirportResolver = { initAirportResolver, resolveInto };
})();
