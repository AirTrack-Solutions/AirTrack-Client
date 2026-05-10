/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

document.addEventListener("DOMContentLoaded", function () {
    function setupLiveFilter(inputId, tableBodyId, searchType) {
        const input = document.getElementById(inputId);
        const tableBody = document.getElementById(tableBodyId);

        if (!input || !tableBody) return;

        input.addEventListener("input", function () {
            const searchText = input.value.trim();

            // Send AJAX request to Flask backend
            fetch(`/search?type=${searchType}&search=${encodeURIComponent(searchText)}&page=1`)
                .then(response => response.text())
                .then(html => {
                    tableBody.innerHTML = html; // Update table content dynamically
                })
                .catch(error => console.error("Search error:", error));
        });
    }

    // Initialize Live Filtering for Airlines and Aircraft tables
    setupLiveFilter("airlineSearch", "airlines-tbody", "airline");
    setupLiveFilter("aircraftSearch", "aircraft-tbody", "aircraft");
});
