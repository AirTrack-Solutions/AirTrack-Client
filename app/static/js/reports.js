/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ reports.js loaded");  // Debugging

    var disclaimerModal = document.getElementById("disclaimerModal");

    if (disclaimerModal) {
        console.log("✅ Found disclaimerModal in the HTML");

        // ✅ Ensure Bootstrap modal is properly initialized
        var modalInstance = new bootstrap.Modal(disclaimerModal);

        // ✅ Fetch disclaimer setting from the server
        fetch("/get_disclaimer_status")
            .then(response => response.json())
            .then(data => {
                console.log("🔍 Disclaimer Status:", data.show_disclaimer);
                if (data.show_disclaimer) {
                    modalInstance.show();  // Show the modal only if it's enabled
                }
            })
            .catch(error => console.error("❌ Fetch Error:", error));

        // ✅ Handle the "OK" button click
        document.getElementById("acceptDisclaimer").addEventListener("click", function () {
            if (document.getElementById("hideDisclaimer").checked) {
                fetch("/hide_disclaimer", { method: "POST" })
                    .then(response => response.json())
                    .then(data => console.log("✅ Disclaimer setting updated:", data));
            }
            modalInstance.hide();
        });

    } else {
        console.log("❌ Modal not found in the HTML");
    }
});
