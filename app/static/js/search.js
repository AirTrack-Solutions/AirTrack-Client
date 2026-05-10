/*
 * AirTrack 1.0.0 'Wilbur' — Release 300
 * Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
 * SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
 */

// static/js/search.js

$(document).ready(function () {
    console.log("✅ jQuery Loaded and Ready!");

    // Airline Search
    $("#airlineSearch").on("input", function () {
        let query = $(this).val().trim();
        console.log("🔍 Searching Airlines:", query);

        $.get("/search_unified", { type: "airlines", search: query })
            .done(function (partialHtml) {
                console.log("✅ AJAX Response for Airlines");
                $("#airlines-tbody").html(partialHtml);
            })
            .fail(function (error) {
                console.error("❌ AJAX Failed:", error);
            });
    });

    // Aircraft Search (FIXED with add button fallback)
    $("#aircraftSearch").on("input", function () {
        let query = $(this).val().trim();
        console.log("🔍 Searching Aircraft:", query);

        $.get("/search_unified", { type: "aircraft", search: query })
            .done(function (partialHtml) {
                console.log("✅ AJAX Response for Aircraft");

                let tbody = $("#aircraft-tbody");
                let newRows = $(partialHtml).find("tr");

                tbody.html(newRows);

                // Check for the "no results" row using colspan=10
                if (tbody.find('td[colspan="10"]').length > 0) {
                    $(".add-aircraft-container").fadeIn();
                } else {
                    $(".add-aircraft-container").fadeOut();
                }
            })
            .fail(function (error) {
                console.error("❌ AJAX Failed:", error);
            });
    });

    // Aircraft Filter by Airline
    $("#apply-filter-btn").on("click", function () {
        let airline = $("#airline-filter").val();
        let query = $("#search-box").val().trim();

        console.log("🔍 Applying Filter for Airline:", airline);

        $.get("/filter_aircraft", { airline: airline, search: query })
            .done(function (data) {
                $("#aircraft-tbody").html(data.filtered_rows);
                $("#pagination-container").html(data.pagination_html);
            })
            .fail(function (jqXHR, textStatus, errorThrown) {
                console.error("❌ AJAX Failed:", textStatus, errorThrown);
            });
    });
});
