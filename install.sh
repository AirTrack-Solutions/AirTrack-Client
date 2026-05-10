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

    # Copy example and substitute all credential placeholders
    sed \
        -e "s|your-secret-key-here|${SECRET_KEY}|" \
        -e "s|DB_PASSWORD=changeme$|DB_PASSWORD=${DB_PASSWORD}|" \
        -e "s|DB_ROOT_PASSWORD=changeme-root|DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD}|" \
        -e "s|MYSQL_PASSWORD=changeme|MYSQL_PASSWORD=${DB_PASSWORD}|" \
        -e "s|MYSQL_ROOT_PASSWORD=changeme-root|MYSQL_ROOT_PASSWORD=${DB_ROOT_PASSWORD}|" \
        env.client.example > .env.client

    echo " Configuration generated."
else
    echo " Existing .env.client found — skipping generation."
fi

# ── Ensure license.lic is a file, not a directory ────────────────────────────
# Docker creates a directory if the bind-mount target doesn't exist.
# We pre-create the file so Docker always finds a file to mount.
mkdir -p app/config
if [ -d app/config/license.lic ]; then
    rmdir app/config/license.lic 2>/dev/null && touch app/config/license.lic
    echo " Fixed: license.lic was a directory — replaced with empty file."
elif [ ! -f app/config/license.lic ]; then
    touch app/config/license.lic
fi

# Remove placeholder license content if present
if [ -f app/config/license.lic ]; then
    CONTENT=$(cat app/config/license.lic)
    if echo "$CONTENT" | grep -q "REPLACE_WITH_YOUR_LICENSE"; then
        echo "" > app/config/license.lic
        echo " Cleared placeholder license."
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
