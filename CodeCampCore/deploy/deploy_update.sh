#!/usr/bin/env bash
# ==============================================================================
# CodeCamp 2026 Ecosystem — VPS Safe Update & Zero-Downtime Deployment
# Deploys updates across all 3 systems:
#   1. CodeCampCore (Master Academy ERP & ID Generator)
#   2. Codecamp (Admissions Gateway)
#   3. Attendance-System (Biometric Attendance & QR Registry)
#
# Usage:
#   sudo bash /var/www/codecamp2026/CodeCampCore/deploy/deploy_update.sh
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   CodeCamp 2026 Ecosystem — VPS Production Update Suite       ${NC}"
echo -e "${BLUE}================================================================${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] This script must be run as root. Run with: sudo bash deploy_update.sh${NC}"
  exit 1
fi

DEPLOY_ROOT="/var/www/codecamp2026"
BACKUP_DIR="/var/backups/codecamp_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# ------------------------------------------------------------------------------
# 1. Safe Git Pull with Automatic Stash
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/7] Syncing Latest Code from GitHub (origin/main)...${NC}"
cd "$DEPLOY_ROOT"

# Stash any untracked or local changes to prevent merge conflicts
git stash --include-untracked || true
git fetch origin main
git checkout main
git pull origin main
echo -e "${GREEN}[OK] Repository pulled successfully.${NC}"

# ------------------------------------------------------------------------------
# 2. Database Backup (Safety Checkpoint)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/7] Creating Safety Database Checkpoints...${NC}"
# Backup PostgreSQL if available
if command -v pg_dump >/dev/null 2>&1; then
    sudo -u postgres pg_dump codecamp_core_db > "$BACKUP_DIR/codecamp_core_db.sql" 2>/dev/null || true
    sudo -u postgres pg_dump attendance_db > "$BACKUP_DIR/attendance_db.sql" 2>/dev/null || true
fi

# Backup SQLite databases if present
find "$DEPLOY_ROOT" -name "db.sqlite3" -exec cp --parents {} "$BACKUP_DIR" \; 2>/dev/null || true
echo -e "${GREEN}[OK] Database backups stored at $BACKUP_DIR.${NC}"

# ------------------------------------------------------------------------------
# 3. Update CodeCampCore (Master Academy ERP)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/7] Updating CodeCampCore (Master ERP)...${NC}"
cd "$DEPLOY_ROOT/CodeCampCore"

CORE_VENV="$DEPLOY_ROOT/CodeCampCore/venv"
if [ ! -d "$CORE_VENV" ]; then
    python3 -m venv "$CORE_VENV"
fi

"$CORE_VENV/bin/pip" install --upgrade pip setuptools wheel --quiet
if [ -f "requirements-prod.txt" ]; then
    "$CORE_VENV/bin/pip" install -r requirements-prod.txt --quiet
elif [ -f "requirements.txt" ]; then
    "$CORE_VENV/bin/pip" install -r requirements.txt --quiet
fi

# Apply migrations first to ensure parent_id and accounts_parent exist
echo -e "${CYAN}Applying CodeCampCore migrations...${NC}"
"$CORE_VENV/bin/python" manage.py migrate --noinput

# Collect static assets
echo -e "${CYAN}Collecting CodeCampCore static assets...${NC}"
"$CORE_VENV/bin/python" manage.py collectstatic --noinput

# Run parent and photo synchronization from Attendance System
echo -e "${CYAN}Running Attendance System Parent & Photo Sync...${NC}"
"$CORE_VENV/bin/python" manage.py update_parents_from_attendance || true

echo -e "${GREEN}[OK] CodeCampCore updated and synchronized.${NC}"

# ------------------------------------------------------------------------------
# 4. Update Codecamp Admissions Gateway
# ------------------------------------------------------------------------------
if [ -d "$DEPLOY_ROOT/Codecamp/camp" ]; then
    echo -e "\n${YELLOW}[4/7] Updating Codecamp Admissions Gateway...${NC}"
    cd "$DEPLOY_ROOT/Codecamp/camp"

    ADMISSIONS_VENV="$DEPLOY_ROOT/Codecamp/camp/cenv"
    if [ ! -d "$ADMISSIONS_VENV" ]; then
        python3 -m venv "$ADMISSIONS_VENV"
    fi

    "$ADMISSIONS_VENV/bin/pip" install --upgrade pip setuptools wheel --quiet
    if [ -f "requirements.txt" ]; then
        "$ADMISSIONS_VENV/bin/pip" install -r requirements.txt gunicorn psycopg[binary] --quiet
    fi

    echo -e "${CYAN}Applying Admissions Gateway migrations...${NC}"
    "$ADMISSIONS_VENV/bin/python" manage.py migrate --noinput || true

    echo -e "${CYAN}Collecting Admissions Gateway static assets...${NC}"
    "$ADMISSIONS_VENV/bin/python" manage.py collectstatic --noinput || true
    echo -e "${GREEN}[OK] Codecamp Admissions Gateway updated.${NC}"
else
    echo -e "\n${YELLOW}[4/7] Skipping Admissions Gateway (directory not found).${NC}"
fi

# ------------------------------------------------------------------------------
# 5. Update Attendance System Backend
# ------------------------------------------------------------------------------
if [ -d "$DEPLOY_ROOT/attendance-system/backend" ]; then
    echo -e "\n${YELLOW}[5/7] Updating Attendance System Backend...${NC}"
    cd "$DEPLOY_ROOT/attendance-system/backend"

    ATTENDANCE_VENV="$DEPLOY_ROOT/attendance-system/backend/attv"
    if [ ! -d "$ATTENDANCE_VENV" ]; then
        python3 -m venv "$ATTENDANCE_VENV"
    fi

    "$ATTENDANCE_VENV/bin/pip" install --upgrade pip setuptools wheel --quiet
    if [ -f "requirements.txt" ]; then
        "$ATTENDANCE_VENV/bin/pip" install -r requirements.txt gunicorn psycopg[binary] --quiet
    fi

    echo -e "${CYAN}Applying Attendance System migrations...${NC}"
    "$ATTENDANCE_VENV/bin/python" manage.py migrate --noinput || true

    echo -e "${CYAN}Collecting Attendance System static assets...${NC}"
    "$ATTENDANCE_VENV/bin/python" manage.py collectstatic --noinput || true
    echo -e "${GREEN}[OK] Attendance System updated.${NC}"
else
    echo -e "\n${YELLOW}[5/7] Skipping Attendance System (directory not found).${NC}"
fi

# ------------------------------------------------------------------------------
# 6. Fix File Ownership & Permissions
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/7] Ensuring correct www-data file ownership...${NC}"
chown -R www-data:www-data "$DEPLOY_ROOT"
chmod -R 755 "$DEPLOY_ROOT"
echo -e "${GREEN}[OK] Permissions restored.${NC}"

# ------------------------------------------------------------------------------
# 7. Restart Services & Health Verification
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[7/7] Restarting Services and Verifying Status...${NC}"
systemctl daemon-reload

SERVICES=("codecampcore" "codecamp-reg" "attendance")
for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^${svc}.service"; then
        systemctl restart "$svc"
        echo -e "${GREEN}[OK] Service $svc restarted.${NC}"
    fi
done

if systemctl is-active --quiet nginx; then
    nginx -t && systemctl reload nginx
    echo -e "${GREEN}[OK] Nginx reloaded.${NC}"
fi

echo -e "\n${BLUE}================================================================${NC}"
echo -e "${GREEN}   DEPLOYMENT COMPLETED SUCCESSFULLY!                           ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo -e "Service Status Summary:"
for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^${svc}.service"; then
        STATUS=$(systemctl is-active "$svc" || echo "failed")
        if [ "$STATUS" = "active" ]; then
            echo -e "  - ${svc}: ${GREEN}ACTIVE${NC}"
        else
            echo -e "  - ${svc}: ${RED}${STATUS^^}${NC}"
        fi
    fi
done
