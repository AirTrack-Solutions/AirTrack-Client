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

# ── Bootstrap: clone repo if running via curl rather than from inside it ──────
# When piped through curl | bash the working directory won't have the repo files.
# In that case, clone AirTrack-Client into the current directory first.
if [ ! -f env.client.example ]; then
    echo " Fetching AirTrack..."
    REPO_URL="https://github.com/Subhuti/AirTrack-Client.git"
    TMP_DIR=$(mktemp -d)
    git clone --depth=1 "$REPO_URL" "$TMP_DIR" 2>&1 | grep -v "^$"
    if [ $? -ne 0 ]; then
        echo " ERROR: Failed to clone AirTrack-Client from GitHub."
        echo " Check your internet connection and try again."
        rm -rf "$TMP_DIR"
        exit 1
    fi
    rsync -a "$TMP_DIR/" .
    rm -rf "$TMP_DIR"
    echo " Done."
    echo ""
fi

# ── Sanity check ─────────────────────────────────────────────────────────────
if [ ! -f env.client.example ]; then
    echo " ERROR: env.client.example not found after clone."
    echo " Something went wrong — please try again."
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

# ── Desktop shortcut ──────────────────────────────────────────────────────────
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_PATH="$INSTALL_DIR/app/static/logo.ico"
DESKTOP_ENTRY="[Desktop Entry]
Version=1.0
Type=Application
Name=AirTrack Logbook
Comment=Open AirTrack Logbook
Exec=xdg-open http://localhost:5000
Icon=$ICON_PATH
Terminal=false
Categories=Utility;"

CREATED_SHORTCUT=0

# App menu entry
if [ -d "$HOME/.local/share/applications" ] || mkdir -p "$HOME/.local/share/applications" 2>/dev/null; then
    echo "$DESKTOP_ENTRY" > "$HOME/.local/share/applications/airtrack.desktop"
    chmod +x "$HOME/.local/share/applications/airtrack.desktop"
    CREATED_SHORTCUT=1
fi

# Desktop icon (only if ~/Desktop exists — headless installs won't have it)
if [ -d "$HOME/Desktop" ]; then
    echo "$DESKTOP_ENTRY" > "$HOME/Desktop/AirTrack.desktop"
    chmod +x "$HOME/Desktop/AirTrack.desktop"
    CREATED_SHORTCUT=1
fi

if [ "$CREATED_SHORTCUT" -eq 1 ]; then
    echo " Desktop shortcut created."
    echo ""
fi
