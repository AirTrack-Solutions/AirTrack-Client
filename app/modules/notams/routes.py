"""
NOTAM Logbook routes.
"""

from __future__ import annotations

from flask import Blueprint, render_template_string

notams_bp = Blueprint("notams", __name__, url_prefix="/notams")


DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AirTrack NOTAMs</title>
  <style>
    body {
      margin: 0;
      background: #0d1117;
      color: #e6edf3;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      max-width: 960px;
      margin: 0 auto;
      padding: 32px;
    }
    .card {
      border: 1px solid #2f81f7;
      background: #111923;
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 0 24px rgba(47,129,247,0.12);
    }
    h1 {
      color: #f0a500;
      margin-top: 0;
    }
    .muted {
      color: #8b949e;
    }
    code {
      color: #79c0ff;
    }
  </style>
</head>
<body>
<main>
  <div class="card">
    <h1>Groundhog Gus NOTAM Desk</h1>
    <p class="muted">Scaffold active. Live database wiring still pending.</p>
    <p>Manual import endpoint:</p>
    <p><code>POST /api/notams/import</code></p>
    <p>Health endpoint:</p>
    <p><code>GET /api/notams/health</code></p>
  </div>
</main>
</body>
</html>
"""


@notams_bp.get("/")
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)
