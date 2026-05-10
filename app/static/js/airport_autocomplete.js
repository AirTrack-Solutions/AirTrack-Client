/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

document.addEventListener("DOMContentLoaded", function () {
  function setupAutocomplete(inputId, hiddenId, suggestionsId) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const suggestions = document.getElementById(suggestionsId);

    if (!input || !hidden || !suggestions) return;

    let timeout = null;

    input.addEventListener("input", function () {
      const query = input.value.trim();
      clearTimeout(timeout);

      if (query.length < 2) {
        suggestions.innerHTML = "";
        suggestions.style.display = "none";
        return;
      }

      timeout = setTimeout(() => {
        fetch(`/airports/search?q=${encodeURIComponent(query)}`)
          .then(response => response.json())
          .then(data => {
            suggestions.innerHTML = "";
            if (data.length === 0) {
              suggestions.style.display = "none";
              return;
            }

            data.forEach(airport => {
              const option = document.createElement("div");
              option.className = "airport-suggestion";
              option.textContent = `${airport.display_name} [${airport.ICAO}]`;
              option.dataset.icao = airport.ICAO;
              option.addEventListener("click", function () {
                input.value = `${airport.display_name}`;
                hidden.value = airport.ICAO;
                suggestions.innerHTML = "";
                suggestions.style.display = "none";
              });
              suggestions.appendChild(option);
            });

            suggestions.style.display = "block";
          })
          .catch(err => {
            console.error("❌ Airport lookup failed:", err);
            suggestions.innerHTML = "";
            suggestions.style.display = "none";
          });
      }, 300);
    });

    document.addEventListener("click", function (e) {
      if (!suggestions.contains(e.target) && e.target !== input) {
        suggestions.innerHTML = "";
        suggestions.style.display = "none";
      }
    });
  }

  setupAutocomplete("departure-input", "departure-hidden", "departure-suggestions");
  setupAutocomplete("arrival-input", "arrival-hidden", "arrival-suggestions");
});
