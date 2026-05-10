/*! ---------------------------------------------------------------------------
 * AirTrack 1.0.0 "Wilbur" — admin.js
 * HUD + gauges + JSON helpers + housekeeping + Git/updates + WebAuthn
 * --------------------------------------------------------------------------- */
console.log("admin.js is alive!");

document.addEventListener("DOMContentLoaded", () => {
  // ---------- Theme & background --------------------------------------------
  const theme = localStorage.getItem("airtrack-theme") || "default";

  document.body.classList.remove("admin-dark", "admin-autumn", "admin-default");
  if (theme === "autumn") {
    document.body.classList.add("admin-autumn");
  } else if (theme === "dark") {
    document.body.classList.add("admin-dark");
  } else {
    document.body.classList.add("admin-default");
  }

  const bg = document.querySelector(".admin-background");
  if (bg) {
    const cockpitImage = `/static/themes/${theme}_cockpit.png`;
    bg.style.backgroundImage = `url('${cockpitImage}')`;
    bg.style.backgroundSize = "cover";
    bg.style.backgroundPosition = "center";
    bg.style.backgroundRepeat = "no-repeat";
  }

  // ---------- Helpers --------------------------------------------------------
  const $ = (sel) => document.querySelector(sel);

  const leftCol = () =>
    document.querySelector(".hud-left .cockpit-hud-column") ||
    document.querySelector(".hud-left");

  const rightCol = () =>
    document.querySelector(".hud-right .cockpit-hud-column") ||
    document.querySelector(".hud-right");

  // NOTE: showModal / hideModal are now defined in admin.html and reused here.

  // --- CSRF helpers (meta tag OR cookie fallback) ----------------------------
  function getCookie(name) {
    return document.cookie.split("; ").reduce((acc, c) => {
      const [k, v] = c.split("=");
      return k === name ? decodeURIComponent(v || "") : acc;
    }, "");
  }

  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    return getCookie("csrf_token") || "";
  }

  // ---------- JSON helpers ---------------------------------------------------
  async function postJSON(url, body, extraHeaders) {
    try {
      const headers = Object.assign(
        {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": getCSRFToken(),
          "X-CSRF-Token": getCSRFToken(),
        },
        extraHeaders || {}
      );

      const res = await fetch(url, {
        method: "POST",
        headers,
        credentials: "same-origin",
        body: JSON.stringify(body || {}),
      });

      const status = res.status;
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const raw = await res.text();

      if (ct.includes("application/json")) {
        try {
          const parsed = JSON.parse(raw);
          return parsed;
        } catch (e) {
          return {
            status: "error",
            detail: "Invalid JSON in response",
            http_status: status,
          };
        }
      }

      return {
        status: "error",
        detail:
          `HTTP ${status}: ` +
          (raw.slice(0, 400) || res.statusText || "Non-JSON response"),
        http_status: status,
      };
    } catch (err) {
      return {
        status: "error",
        detail:
          "Network error: " +
          (err && err.message ? err.message : String(err || "unknown")),
      };
    }
  }

  async function getJSON(url) {
    try {
      const res = await fetch(url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const raw = await res.text();
      if (ct.includes("application/json")) {
        try {
          return JSON.parse(raw);
        } catch {
          return {};
        }
      }
      return {};
    } catch {
      return {};
    }
  }

  // ---------- Small DOM helper for cockit HUD buttons -----------------------
  function insertHudButton(columnEl, id, text, onClick, opts) {
    const options = opts || {};
    const position = options.position || "top";
    const extraClass = options.extraClass || "";

    if (!columnEl || document.getElementById(id)) return;

    const form = document.createElement("form");
    form.className = "cockpit-hud-form";
    form.addEventListener("submit", (e) => e.preventDefault());

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = id;
    btn.className = `cockpit-hud-button ${extraClass}`.trim();
    btn.textContent = text;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (onClick) onClick();
    });

    form.appendChild(btn);

    if (position === "top") {
      columnEl.insertBefore(form, columnEl.firstChild);
    } else {
      columnEl.appendChild(form);
    }
  }

  // ---------- In-page Logs Viewer (legacy: viewLogs()) ----------------------
  (function setupLogsViewer() {
    function ensureLogsModal() {
      let modal = document.getElementById("adminLogsModal");
      if (!modal) {
        modal = document.createElement("div");
        modal.id = "adminLogsModal";
        modal.className = "cockpit-modal";
        modal.innerHTML = `
          <div class="cockpit-modal-content" style="max-width:80vw; max-height:75vh; overflow:auto; text-align:left">
            <h3 style="margin-top:0">✈️ AirTrack Logs</h3>
            <div style="margin:6px 0; display:flex; gap:8px; align-items:center;">
              <label style="font-size:0.9em">Tail:</label>
              <select id="logsTailN" class="cockpit-hud-button" style="padding:2px 6px;">
                <option value="200">200</option>
                <option value="500" selected>500</option>
                <option value="1000">1000</option>
              </select>
              <button type="button" id="logsRefresh" class="cockpit-hud-button">Refresh</button>
            </div>
            <div id="admin-logs-body" style="white-space:pre-wrap; font-family:monospace; line-height:1.25; max-height:58vh; overflow:auto;">Loading…</div>
            <div style="margin-top:12px; text-align:center">
              <button type="button" class="cockpit-hud-button" id="adminLogsClose">Close</button>
            </div>
          </div>`;
        document.body.appendChild(modal);

        modal
          .querySelector("#adminLogsClose")
          .addEventListener("click", () => {
            modal.style.display = "none";
          });

        modal.addEventListener("click", (e) => {
          if (e.target === modal) modal.style.display = "none";
        });

        document.addEventListener("keydown", (e) => {
          if (e.key === "Escape") modal.style.display = "none";
        });

        modal
          .querySelector("#logsRefresh")
          .addEventListener("click", () => {
            const n =
              document.getElementById("logsTailN").value || "500";
            loadLogs(parseInt(n, 10) || 500);
          });
      }
      return modal;
    }

    function esc(s) {
      return (s || "").replace(/[&<>"]/g, (c) => {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c;
      });
    }

    async function tailLogs(tailN) {
      try {
        const res = await fetch(
          `/admin_tools/logs/tail?pattern=${encodeURIComponent(
            "*.log*"
          )}&tail=${tailN}`,
          {
            headers: { Accept: "application/json" },
          }
        );
        if (!res.ok) return null;
        return await res.json();
      } catch {
        return null;
      }
    }

    async function loadLogs(tailN) {
      const modal = ensureLogsModal();
      const body = modal.querySelector("#admin-logs-body");
      body.textContent = "Loading…";

      const data = await tailLogs(tailN);
      if (
        !data ||
        data.status !== "success" ||
        !Array.isArray(data.logs) ||
        data.logs.length === 0
      ) {
        body.innerHTML =
          "<em>No logs found in /app/logs (or endpoint missing).</em>";
        return;
      }

      body.innerHTML = data.logs
        .map(
          (l) => `
        <details open style="margin:8px 0;">
          <summary><strong>${esc(l.name)}</strong> <small>${esc(
            l.mtime
          )} • ${l.size} bytes</small></summary>
          <pre style="background:#0a0a0a; padding:8px; border-radius:6px; overflow:auto; max-height:28vh">${esc(
            l.content
          )}</pre>
        </details>
      `
        )
        .join("");
    }

    // Legacy global, in case something still calls it:
    window.viewLogs = function () {
      const modal = ensureLogsModal();
      modal.style.display = "block";
      const n = parseInt(
        (document.getElementById("logsTailN") || {}).value || "500",
        10
      );
      loadLogs(n || 500);
    };
  })();

  // ---------- Git buttons ----------------------------------------------------
  function injectGitButtons() {
    // Commit (left / top)
    insertHudButton(
      leftCol(),
      "gitCommitBtn",
      "Commit",
      async () => {
        const defaultMsg =
          new Date().toISOString().slice(0, 10) + " - cockpit change";
        const message = prompt("Commit message:", defaultMsg);
        if (message == null || message.trim() === "") return;

        if (typeof showModal === "function") showModal("Committing…");

        const data = await postJSON("/admin_tools/git_commit", {
          message,
        });

        if (!data || data.status === "error") {
          if (typeof showModal === "function") {
            showModal(
              "❌ Commit failed: " +
                (data && data.detail ? data.detail : "Unknown error")
            );
          }
        } else if (data.status === "noop") {
          if (typeof showModal === "function") {
            showModal("ℹ️ Nothing to commit.");
          }
        } else {
          if (typeof showModal === "function") {
            showModal("✅ Commit complete.");
          }
        }

        if (typeof hideModal === "function") {
          setTimeout(hideModal, 2500);
        }
      },
      { position: "top" }
    );

    // Push (right / top)
    insertHudButton(
      rightCol(),
      "gitPushBtn",
      "Push",
      async () => {
        if (typeof showModal === "function") {
          showModal("Pushing to origin…");
        }

        const data = await postJSON("/admin_tools/git_push", {});

        if (!data || data.status === "error") {
          if (typeof showModal === "function") {
            showModal(
              "❌ Push failed: " +
                (data && data.detail ? data.detail : "Unknown error")
            );
          }
        } else {
          if (typeof showModal === "function") {
            showModal("✅ Push complete.");
          }
        }

        if (typeof hideModal === "function") {
          setTimeout(hideModal, 2500);
        }
      },
      { position: "top" }
    );
  }

  // ---------- Graceful Shut Down (confirm only) ------------------------------
  function injectShutdownButton() {
    insertHudButton(
      rightCol(),
      "shutdownBtn",
      "Shut Down",
      async () => {
        const sure = confirm(
          "Shut down AirTrack now?\n\nThis stops the server process."
        );
        if (!sure) return;

        if (typeof showModal === "function") {
          showModal("Shutting down AirTrack…");
        }

        const data = await postJSON("/admin_tools/shutdown", {});

        if (!data || data.status === "error") {
          if (typeof showModal === "function") {
            showModal(
              "❌ Shutdown failed: " +
                (data && data.detail ? data.detail : "Unknown error")
            );
          }
        } else {
          if (typeof showModal === "function") {
            showModal("🛫 Server is stopping…");
          }
        }

        if (typeof hideModal === "function") {
          setTimeout(hideModal, 3000);
        }
      },
      { position: "top" }
    );
  }

  // ---------- Gauges ---------------------------------------------------------
  document.querySelectorAll(".gauge").forEach((gauge) => {
    const needle = gauge.querySelector(".needle");

    if (!gauge.querySelector(".tick")) {
      for (let i = 0; i <= 8; i++) {
        const tick = document.createElement("div");
        tick.className = `tick tick-${i}`;
        gauge.appendChild(tick);
      }
    }

    const rawCount = gauge.dataset.count;
    const count = parseFloat(rawCount) || 0;
    const valueEl = gauge.querySelector(".gauge-value");

    let max = 100;
    if (count > 100) max = 1000;
    if (count > 1000) max = 10000;
    if (count > 10000) max = 100000;

    const clamped = Math.min(count, max);
    const percent = (clamped / max) * 100;
    const angle = (percent / 100) * 270 - 135;

    if (needle) {
      requestAnimationFrame(() => {
        needle.style.transform = `rotate(${angle}deg)`;
      });
    }
    if (valueEl) valueEl.textContent = count;
  });

  // ---------- Housekeeping / Clean Up ----------------------------------------
  function formatBytes(n) {
    const num = Number(n) || 0;
    if (num <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB", "PB"];
    let v = num;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(1)} ${units[i]}`;
  }

  function summariseCleanup(payload) {
    if (!payload || typeof payload !== "object") {
      return { bytes: 0, files: 0 };
    }
    const backups = payload.deleted_backups || {};
    const exports = payload.deleted_exports || {};
    const logs = payload.rotated_logs || {};

    const bytes =
      (Number(backups.bytes) || 0) +
      (Number(exports.bytes) || 0) +
      (Number(logs.bytes_saved) || 0);

    const files =
      (Number(backups.files) || 0) +
      (Number(exports.files) || 0) +
      (Number(logs.compressed) || 0) +
      (Number(logs.deleted) || 0);

    return { bytes, files };
  }

  function injectHousekeepingButton() {
    const lc = leftCol();
    if (!lc || document.getElementById("housekeepBtn")) return;

    insertHudButton(
      lc,
      "housekeepBtn",
      "Clean Up",
      async () => {
        const retention = prompt(
          "Delete temp/cache/exports older than how many days?",
          "14"
        );
        if (retention === null) return;

        const days = Math.max(0, parseInt(retention, 10) || 14);

        if (typeof showModal === "function") {
          showModal("Scanning… (preview)");
        }

        const preview = await postJSON("/admin_tools/housekeeping", {
          dry_run: true,
          retention_days: days,
        });

        if (!preview || preview.status === "error") {
          if (typeof showModal === "function") {
            showModal(
              "❌ Cleanup preview failed." +
                (preview && preview.detail
                  ? "\n" + preview.detail
                  : "")
            );
            setTimeout(() => {
              if (typeof hideModal === "function") hideModal();
            }, 2500);
          }
          return;
        }

        const sumPrev = summariseCleanup(preview);
        const freed = formatBytes(sumPrev.bytes);
        const files = sumPrev.files;

        const sure = confirm(
          `This will remove/compress about ${files} files\n` +
            `and free roughly ${freed}.\n\nProceed?`
        );
        if (!sure) {
          if (typeof hideModal === "function") hideModal();
          return;
        }

        if (typeof showModal === "function") {
          showModal("Cleaning up…");
        }

        const run = await postJSON("/admin_tools/housekeeping", {
          dry_run: false,
          retention_days: days,
        });

        if (!run || run.status === "error") {
          if (typeof showModal === "function") {
            showModal(
              "❌ Cleanup failed." +
                (run && run.detail ? "\n" + run.detail : "")
            );
          }
        } else {
          const sumRun = summariseCleanup(run);
          const freedRun = formatBytes(sumRun.bytes);
          if (typeof showModal === "function") {
            showModal(`✅ Cleanup complete. Freed around ${freedRun}.`);
          }
        }

        if (typeof hideModal === "function") {
          setTimeout(hideModal, 2800);
        }
      },
      { position: "bottom" }
    );
  }

  // ---------- ONE definitive flag tooltip (custom overlay) -------------------
  (function flagOverlayTooltips() {
    const css = document.createElement("style");
    css.textContent = `
      .at-flag-tip {
        position: fixed;
        z-index: 99999;
        pointer-events: none;
        font: 12px/1.3 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        background: rgba(20,20,20,.92);
        color: #fff;
        padding: 6px 8px;
        border-radius: 6px;
        box-shadow: 0 4px 14px rgba(0,0,0,.35);
        transform: translate(8px, 12px);
        white-space: nowrap;
      }
      img.flag-img, img[src*="/flags/"] { pointer-events: auto !important; }
    `;
    document.head.appendChild(css);

    const dn =
      window.Intl && Intl.DisplayNames
        ? new Intl.DisplayNames(
            [navigator.language || "en"],
            { type: "region" }
          )
        : null;

    const countryName = (iso) => {
      try {
        return dn ? dn.of(iso) : "";
      } catch {
        return "";
      }
    };

    const isoFromSrc = (src) => {
      const m =
        (src || "").match(
          /\/flags\/([A-Za-z]{2,3})\.(?:svg|png|gif|jpe?g)(?:\?.*)?$/i
        ) ||
        (src || "").match(
          /\/([A-Za-z]{2,3})\.(?:svg|png|gif|jpe?g)(?:\?.*)?$/i
        );
      return m ? m[1].toUpperCase() : "";
    };

    let tip;

    function ensureTip() {
      if (!tip) {
        tip = document.createElement("div");
        tip.className = "at-flag-tip";
        tip.style.display = "none";
        tip.textContent = "";
        document.body.appendChild(tip);
      }
      return tip;
    }

    function showTip(text, x, y) {
      const el = ensureTip();
      el.textContent = text || "";
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
      el.style.display = "block";
    }

    function hideTip() {
      if (tip) tip.style.display = "none";
    }

    function bindFlag(img) {
      if (!(img instanceof HTMLImageElement)) return;
      if (img.__atFlagBound) return;
      img.__atFlagBound = true;

      const isoAttr = (
        img.dataset.cc ||
        img.dataset.country ||
        img.dataset.iso ||
        ""
      ).toUpperCase();

      const iso = isoAttr || isoFromSrc(img.getAttribute("src") || "");
      const name = iso ? countryName(iso) : "";
      const label = iso ? (name ? `${name} (${iso})` : iso) : (img.alt || "").trim();

      if (!label) return;

      img.addEventListener("mouseenter", (e) => {
        showTip(label, e.clientX + 10, e.clientY + 14);
      });
      img.addEventListener("mousemove", (e) => {
        if (!tip || tip.style.display === "none") return;
        tip.style.left = `${e.clientX + 10}px`;
        tip.style.top = `${e.clientY + 14}px`;
      });
      img.addEventListener("mouseleave", hideTip);
    }

    function scan() {
      document
        .querySelectorAll('img.flag-img, img[src*="/flags/"]')
        .forEach(bindFlag);
    }

    scan();

    new MutationObserver((muts) => {
      for (const m of muts) {
        (m.addedNodes || []).forEach((n) => {
          if (
            n instanceof HTMLImageElement &&
            (n.classList.contains("flag-img") ||
              (n.getAttribute("src") || "").includes("/flags/"))
          ) {
            bindFlag(n);
          } else if (n instanceof HTMLElement) {
            n
              .querySelectorAll &&
              n
                .querySelectorAll('img.flag-img, img[src*="/flags/"]')
                .forEach(bindFlag);
          }
        });
      }
    }).observe(document.body, { childList: true, subtree: true });
  })();

  // ---------- Boot / feature gating -----------------------------------------
  const URLS = window.AIRTRACK || {};
  const FLAGS = window.AIRTRACK_FLAGS || {};


  injectShutdownButton();
});
// --- BEGIN: Invisible Server Elevation (Ctrl+Alt+S, no UI) ---
(function () {
  if (window.__airtrackSilentServerBind) return;
  window.__airtrackSilentServerBind = true;

  async function post(u, p) {
    try {
      const r = await fetch(u, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p || {}),
        credentials: "same-origin",
      });
      try {
        return await r.json();
      } catch {
        return {};
      }
    } catch {
      return {};
    }
  }

  function b64urlToBuf(b64url) {
    const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(b64);
    const buf = new ArrayBuffer(raw.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < raw.length; i++) view[i] = raw.charCodeAt(i);
    return buf;
  }

  function bufToB64url(buf) {
    const bin = String.fromCharCode(...new Uint8Array(buf));
    return btoa(bin)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  }

  async function silentElevate(timeoutMs) {
    const begin = await post("/server_auth/login/begin", {});
    if (!begin || !begin.ok || !begin.options) return;

    const opts = begin.options;
    opts.challenge = b64urlToBuf(opts.challenge);

    if (Array.isArray(opts.allowCredentials)) {
      opts.allowCredentials = opts.allowCredentials.map((c) => ({
        type: "public-key",
        id: b64urlToBuf(c.id),
        transports: ["usb", "nfc", "ble", "internal"],
      }));
    }

    const ac =
      "AbortController" in window ? new AbortController() : null;
    const t = setTimeout(() => {
      try {
        ac && ac.abort();
      } catch (e) {}
    }, timeoutMs || 20000);

    let assertion;
    try {
      assertion = await navigator.credentials.get({
        publicKey: opts,
        signal: ac ? ac.signal : undefined,
      });
    } catch (e) {
      clearTimeout(t);
      return;
    }
    clearTimeout(t);
    if (!assertion) return;

    const cred = {
      id: assertion.id,
      rawId: bufToB64url(assertion.rawId),
      type: assertion.type,
      response: {
        authenticatorData: bufToB64url(
          assertion.response.authenticatorData
        ),
        clientDataJSON: bufToB64url(assertion.response.clientDataJSON),
        signature: bufToB64url(assertion.response.signature),
        userHandle: assertion.response.userHandle
          ? bufToB64url(assertion.response.userHandle)
          : null,
      },
      clientExtensionResults: assertion.getClientExtensionResults
        ? assertion.getClientExtensionResults()
        : {},
    };

    await post("/server_auth/login/finish", { credential: cred });
  }

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.altKey && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      e.stopPropagation();
      silentElevate(20000);
    }
  });
})();
// --- END: Invisible Server Elevation ---
