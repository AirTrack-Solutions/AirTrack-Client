#!/bin/bash
echo ""
echo " ================================================"
echo "  AirTrack Solutions - First Time Setup"
echo " ================================================"
echo ""
echo " This will build and start AirTrack for the first time."
echo " This may take several minutes. Please be patient."
echo ""
read -p " Press Enter to continue..."
echo ""

# ── Check for env.client.example ─────────────────────────────────────────────
if [ ! -f env.client.example ]; then
    echo " ERROR: env.client.example not found."
    echo " Please ensure you have extracted all files correctly."
    echo ""
    exit 1
fi

# ── Generate .env.client if not already present ───────────────────────────────
if [ ! -f .env.client ]; then

    echo " Generating secure configuration..."

    # Auto-generate credentials
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    DB_ROOT_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")

    # Copy example and substitute placeholders
    sed \
        -e "s|your-secret-key-here|${SECRET_KEY}|" \
        -e "s|DB_PASSWORD=changeme$|DB_PASSWORD=${DB_PASSWORD}|" \
        -e "s|DB_ROOT_PASSWORD=changeme-root|DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD}|" \
        env.client.example > .env.client

    # Write .env for docker-compose variable interpolation
    # (docker-compose reads ${VAR} references from .env, not from env_file)
    printf "DB_NAME=airtrack\nDB_USER=airtrack\nDB_PASSWORD=%s\nDB_ROOT_PASSWORD=%s\nGIT_REMOTE=https://github.com/Subhuti/AirTrack-Client.git\n" \
        "${DB_PASSWORD}" "${DB_ROOT_PASSWORD}" > .env

    echo " Configuration generated."
else
    echo " Existing .env.client found — skipping generation."
    # Regenerate .env from .env.client in case it was lost
    if [ ! -f .env ]; then
        DB_PASSWORD=$(grep "^DB_PASSWORD=" .env.client | cut -d= -f2)
        DB_ROOT_PASSWORD=$(grep "^DB_ROOT_PASSWORD=" .env.client | cut -d= -f2)
        printf "DB_NAME=airtrack\nDB_USER=airtrack\nDB_PASSWORD=%s\nDB_ROOT_PASSWORD=%s\nGIT_REMOTE=https://github.com/Subhuti/AirTrack-Client.git\n" \
            "${DB_PASSWORD}" "${DB_ROOT_PASSWORD}" > .env
    fi
fi

# ── Remove placeholder license ────────────────────────────────────────────────
if [ -f app/config/license.lic ]; then
    CONTENT=$(cat app/config/license.lic)
    if echo "$CONTENT" | grep -q "REPLACE_WITH_YOUR_LICENSE"; then
        rm app/config/license.lic
        echo " Removed placeholder license."
    fi
fi

# ── Build and launch ──────────────────────────────────────────────────────────
echo ""
echo " Building AirTrack..."
echo ""
docker compose -f docker-compose.client.yml up --build -d 2>&1 | grep -v "variable is not set"

if [ $? -ne 0 ]; then
    echo ""
    echo " ERROR: Setup failed."
    echo " Make sure Docker is installed and running, then try again."
    echo ""
    exit 1
fi

echo ""
echo " ================================================"
echo "  Setup complete! AirTrack is running."
echo "  Open your browser and go to:"
echo "  http://localhost:5000"
echo " ================================================"
echo ""
