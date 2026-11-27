# File History: app/utils/photo_ferret.py
Journal Revision: 1
Last Updated: 2026-11-27

## Current State

The distribution copy reads the database password from DB_PASSWORD. Supply the deployment-specific value through the service environment.

## Entry Log


- 2026-11-27 — Removed a bundled database password literal while preparing release artifacts. Python syntax and credential-pattern checks passed. Runtime DB access depends on the environment value. Recover by setting DB_PASSWORD in the service environment.
