/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

document.addEventListener("DOMContentLoaded", () => {
  const theme = localStorage.getItem("airtrack-theme") || "default";
  document.body.classList.add(`theme-${theme}`);

  // Inject admin background div if admin-wrapper exists
  const wrapper = document.querySelector(".admin-wrapper");
  if (wrapper && !document.querySelector(".admin-background")) {
    const bg = document.createElement("div");
    bg.className = "admin-background";
    bg.style.backgroundImage = `url('/static/themes/${theme}_cockpit.png')`;
    bg.style.backgroundSize = "cover";
    bg.style.backgroundPosition = "center";
    bg.style.backgroundRepeat = "no-repeat";
    document.body.insertBefore(bg, wrapper.nextSibling);
  }
});
