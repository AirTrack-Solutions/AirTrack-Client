/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

console.log("🔹 Splash screen script loaded."); 

document.addEventListener("DOMContentLoaded", function() {
    if (document.getElementById("splash")) {
        console.log("✅ Splash screen detected. Timer started."); 

        setTimeout(function() {
            console.log("🕒 10 seconds have passed. Applying fade-out...");
            document.getElementById("splash").classList.add("fade-out");

            setTimeout(function() {
                console.log("🔄 Redirecting now...");
                window.location.href = splashRedirectUrl;
            }, 1000);
        }, 10000);
    }
});
