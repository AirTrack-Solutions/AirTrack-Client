/*! AirTrack Git HUD helpers
 *  Wires CSRF, correct HTTP verbs, and clearer errors for the Git modal.
 */
(function () {
  // -------- CSRF helpers (meta first, cookie fallback) ----------
  function getCookie(name) {
    return document.cookie.split("; ").reduce((acc, c) => {
      const [k, v] = c.split("="); return k === name ? decodeURIComponent(v || "") : acc;
    }, "");
  }
  function getCSRFToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return (m && m.content) || getCookie("csrf_token") || "";
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRFToken": getCSRFToken(),
        "X-CSRF-Token": getCSRFToken()
      },
      body: JSON.stringify(body || {})
    });
    return parseJSON(res);
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" }});
    return parseJSON(res);
  }

  async function parseJSON(res) {
    const raw = await res.text();
    try {
      const json = JSON.parse(raw);
      json.__http_status = res.status;
      return json;
    } catch {
      return { status: "error", detail: `HTTP ${res.status}: ${raw.slice(0,400) || res.statusText}` , __http_status: res.status};
    }
  }

  // -------- UI helpers (simple text sink inside your modal) ------------------
  function $ (sel, root) { return (root || document).querySelector(sel); }
  function showMsg(msg, cls) {
    let box = $("#gitHudMsg");
    if (!box) {
      box = document.createElement("div");
      box.id = "gitHudMsg";
      box.style.marginTop = "8px";
      const modal = document.querySelector(".git-updates-modal") || document.body;
      modal.appendChild(box);
    }
    box.className = cls || "";
    box.textContent = msg;
  }

  // -------- Elevation probe (confirms @require_server) ----------------------
  async function isElevated() {
    try {
      const res = await fetch("/admin_tools/admin/protected/ping".replace("/admin_tools/","/"), { // your route is /admin/protected/ping
        credentials: "same-origin",
        headers: { "Accept":"application/json" }
      });
      if (!res.ok) return false;
      const j = await res.json().catch(()=>({}));
      return !!j.protected;
    } catch { return false; }
  }

  function explain403(where) {
    showMsg(`❌ ${where}: forbidden. This action requires server elevation.`, "text-danger");
    // Tip to elevate via your hidden shortcut:
    console.warn("[AirTrack] Not elevated. Use Ctrl+Alt+S (silent WebAuthn) or set AIRTRACK_ROLE=server on this node, or temporarily remove @require_server for testing.");
  }

  // -------- Public API used by your modal buttons ---------------------------
  const API = {
    async commit(message) {
      if (!message || !message.trim()) { showMsg("Please enter a commit message.", "text-warning"); return; }
      if (!(await isElevated())) { explain403("Commit"); return; }
      showMsg("Committing…");
      const r = await postJSON("/admin_tools/git_commit", { message });
      if (r.status === "success") showMsg("✅ Commit complete.", "text-success");
      else if (r.status === "noop") showMsg("ℹ️ Nothing to commit.", "text-info");
      else if (r.__http_status === 403) explain403("Commit");
      else showMsg(`❌ Commit failed: ${r.detail || "unknown error"}`, "text-danger");
    },

    async push() {
      if (!(await isElevated())) { explain403("Push"); return; }
      showMsg("Pushing to origin…");
      const r = await postJSON("/admin_tools/git_push", {});
      if (r.status === "success") showMsg("✅ Push complete.", "text-success");
      else if (r.__http_status === 403) explain403("Push");
      else showMsg(`❌ Push failed: ${r.detail || "unknown error"}`, "text-danger");
    },

    async check() {  // GET is correct
      showMsg("Checking for updates…");
      const r = await getJSON("/admin_tools/check_updates");
      if (r && (r.emergency_update || (Array.isArray(r.files_needing_update) && r.files_needing_update.length))) {
        showMsg("⬆️ Updates available.", "text-info");
      } else if (r.__http_status === 405) {
        showMsg("❌ METHOD NOT ALLOWED — your UI is calling POST. Use GET for /admin_tools/check_updates.", "text-danger");
      } else {
        showMsg("✅ Up to date.", "text-success");
      }
    },

    async updateNow() { // POST is correct, requires elevation
      if (!(await isElevated())) { explain403("Update"); return; }
      showMsg("Updating…");
      const r = await postJSON("/admin_tools/run_updater?force=true", {});
      if (r.status === "success") { showMsg("✅ Update complete. Reloading…", "text-success"); setTimeout(()=>location.reload(), 1200); }
      else if (r.__http_status === 403) explain403("Update");
      else showMsg(`❌ Update failed: ${r.detail || "unknown error"}`, "text-danger");
    }
  };

  // Expose for your modal buttons:
  window.AirtrackGit = API;
})();
