# File History: app/utils/theme_scanner.py
Journal Revision: 1
Last Updated: 2026-11-24

## Current State
Optional Vintage Brass source implemented; live158/162 available, Windows installer rebuild deferred.

## Known Issues / Future Work
Windows binary requires next installer build; existing user selections retained.

## Entry Log
- Before edit: port new imageless selectable theme; preserve target-specific locking, service and template behaviour. No forced selection or data changes.

- 2026-11-24 implementation complete: optional Vintage Brass metadata has no cockpit/background URL. Scoped CSS supplies plain charcoal surround, brass plaque/navigation/table headings/buttons, clean parchment rows, red destructive buttons and keyboard focus styles. Existing photo themes remain, selected preference unchanged. Generated CSS imports separate versioned stylesheet first; scanner notices code/style changes and returns the cached theme list instead of empty list. Static default is module-relative for native Windows; frozen missing-source path handled. SVG thumbnail is local and no page background image required; legacy Cockpit image layers hidden in this theme. Loader avoids nonexistent vintage cockpit-image requests and marks current navigation. Isolated generator/cache/existing-night-theme regression and JS syntax PASS. Native158/162 generated13choices; HTTP assets/metadata200 and imageless URLs verified. Browser visual acceptance remains user review; no screenshot claimed. No Windows installer rebuild started (credit conservation); Windows source only. Live backups /home/airtrack/backups/vintage-theme-20261124 on158/162 retain old generator/loader/JSON/CSS; restore them and reload web to revert, leaving newer data/settings alone.
