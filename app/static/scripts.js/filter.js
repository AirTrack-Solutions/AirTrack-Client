/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

document.addEventListener("DOMContentLoaded", function () {
    const filterType = document.getElementById("filter_type");
    const filterContainer = document.getElementById("filter_container");
    const applyFilterBtn = document.getElementById("applyFilter");
    const aircraftTableBody = document.getElementById("aircraft-tbody");
    const paginationContainer = document.querySelector(".pagination-container");

    if (!filterType || !filterContainer || !applyFilterBtn) {
        console.error("❌ Filter elements not found!");
        return;
    }

    function updateFilterInput() {
        if (filterType.value === "registration") {
            filterContainer.innerHTML = '<input type="text" id="registration" name="registration" class="form-control" placeholder="Enter Registration">';
        } else if (filterType.value === "airline") {
            filterContainer.innerHTML = '<select id="airlineID" name="airlineID" class="form-control"></select>';
            const newDropdown = document.getElementById("airlineID");
            if (newDropdown) {
                newDropdown.innerHTML = document.getElementById("airlineID").innerHTML;
            }
        }
    }

    applyFilterBtn.addEventListener("click", function () {
        let filterParams = { filter_type: filterType.value };

        if (filterType.value === "registration") {
            filterParams.registration = document.getElementById("registration").value.trim();
        } else if (filterType.value === "airline") {
            filterParams.airlineID = document.getElementById("airlineID").value;
        }

        $.get("/filter", filterParams)
.done(function(response) {
    console.log("✅ Filter Applied Successfully!");
    
    const parser = new DOMParser();
    const doc = parser.parseFromString(response, "text/html");

    // ✅ Only update the table body, not the full page
    document.getElementById("aircraft-tbody").innerHTML = doc.querySelector("#aircraft-tbody").innerHTML;
})
.fail(function(error) {
    console.error("❌ AJAX Filter Failed:", error);
});

    });

    updateFilterInput();
    filterType.addEventListener("change", updateFilterInput);
});
