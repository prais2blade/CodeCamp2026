#!/usr/bin/env bash
# ==============================================================================
# CodeCamp 3-System Ecosystem VPS Automated Deployment Script
# Target OS: Ubuntu 22.04 / 24.04 LTS or Debian 12
# Usage:
#   sudo bash /var/www/codecamp2026/CodeCampCore/deploy/setup_vps.sh
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   CodeCamp 2026 Ecosystem — VPS Production Deployment        ${NC}"
echo -e "${BLUE}================================================================${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] This script must be run as root. Run with: sudo bash setup_vps.sh${NC}"
  exit 1
fi

DEPLOY_ROOT="/var/www/codecamp2026"
LOG_DIR="/var/log/codecamp"

# ------------------------------------------------------------------------------
# 1. System Updates & Dependencies
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/8] Installing Ubuntu System Packages & Libraries...${NC}"
# Remove obsolete or broken third-party PostgreSQL repos if present
rm -f /etc/apt/sources.list.d/pgdg.list* /etc/apt/sources.list.d/*postgresql* 2>/dev/null || true

apt update -y || apt update --fix-missing -y || true
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    postgresql \
    postgresql-contrib \
    libpq-dev \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential \
    curl \
    git \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info

mkdir -p "$LOG_DIR"
chown -R www-data:www-data "$LOG_DIR"

# ------------------------------------------------------------------------------
# 2. Setup PostgreSQL Databases & User
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/8] Configuring PostgreSQL Databases...${NC}"
DB_USER="codecamp_user"
DB_PASS="JetZ@t_2026_LiveSecure"

sudo -u postgres psql <<EOF
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
    ELSE
        ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASS';
    END IF;
END
\$\$;

SELECT 'CREATE DATABASE codecamp_core_db OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'codecamp_core_db')\gexec

SELECT 'CREATE DATABASE codecamp_reg_db OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'codecamp_reg_db')\gexec

SELECT 'CREATE DATABASE attendance_db OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'attendance_db')\gexec
EOF

echo -e "${GREEN}✓ PostgreSQL Databases ready.${NC}"

# ------------------------------------------------------------------------------
# 3. CodeCampCore Setup
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/8] Setting up CodeCampCore (Master ERP)...${NC}"
cd "$DEPLOY_ROOT/CodeCampCore"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

venv/bin/pip install --upgrade pip setuptools wheel
venv/bin/pip install -r requirements-prod.txt

# Copy .env if not present
if [ ! -f ".env" ]; then
    cp deploy/env/core.env.example .env
    sed -i "s/YOUR_STRONG_PASSWORD/$DB_PASS/g" .env
    echo -e "${YELLOW}[!] Created .env for CodeCampCore from template.${NC}"
fi

venv/bin/python manage.py migrate --settings=core.settings.prod
venv/bin/python manage.py collectstatic --noinput --settings=core.settings.prod
venv/bin/python manage.py seed_innovation_hub_courses --tenant-slug lagos-hq --settings=core.settings.prod || true

# ------------------------------------------------------------------------------
# 4. Codecamp Admissions Setup
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/8] Setting up Codecamp Admissions Gateway...${NC}"
cd "$DEPLOY_ROOT/Codecamp/camp"
mkdir -p logs media staticfiles

if [ ! -d "cenv" ]; then
    python3 -m venv cenv
fi

cenv/bin/pip install --upgrade pip setuptools wheel
cenv/bin/pip install -r requirements.txt gunicorn psycopg[binary]

if [ ! -f ".env" ]; then
    cp "$DEPLOY_ROOT/CodeCampCore/deploy/env/codecamp.env.example" .env
    sed -i "s/YOUR_STRONG_PASSWORD/$DB_PASS/g" .env
    echo -e "${YELLOW}[!] Created .env for Codecamp Admissions from template.${NC}"
fi

cenv/bin/python manage.py migrate
cenv/bin/python manage.py collectstatic --noinput || true

# ------------------------------------------------------------------------------
# 5. attendance-system Setup
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/8] Setting up attendance-system Backend...${NC}"
cd "$DEPLOY_ROOT/attendance-system/backend"
mkdir -p logs media staticfiles

if [ ! -d "attv" ]; then
    python3 -m venv attv
fi

attv/bin/pip install --upgrade pip setuptools wheel
attv/bin/pip install -r requirements.txt gunicorn psycopg[binary]

if [ ! -f ".env" ]; then
    cp "$DEPLOY_ROOT/CodeCampCore/deploy/env/attendance.env.example" .env
    sed -i "s/YOUR_STRONG_PASSWORD/$DB_PASS/g" .env
    echo -e "${YELLOW}[!] Created .env for attendance-system from template.${NC}"
fi

attv/bin/python manage.py migrate
attv/bin/python manage.py collectstatic --noinput || true

# ------------------------------------------------------------------------------
# 6. File Permissions
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/8] Fixing Linux User & File Permissions...${NC}"
chown -R www-data:www-data "$DEPLOY_ROOT"
chmod -R 755 "$DEPLOY_ROOT"

# ------------------------------------------------------------------------------
# 7. Systemd Service Registration
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[7/8] Installing & Starting Systemd Services...${NC}"
cp "$DEPLOY_ROOT/CodeCampCore/deploy/systemd/codecampcore.service" /etc/systemd/system/
cp "$DEPLOY_ROOT/CodeCampCore/deploy/systemd/codecamp-reg.service" /etc/systemd/system/
cp "$DEPLOY_ROOT/CodeCampCore/deploy/systemd/attendance.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable codecampcore codecamp-reg attendance
systemctl restart codecampcore codecamp-reg attendance

# ------------------------------------------------------------------------------
# 8. Nginx Reverse Proxy Setup
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[8/8] Configuring Nginx Reverse Proxy...${NC}"
cp "$DEPLOY_ROOT/CodeCampCore/deploy/nginx/codecamp_ecosystem.conf" /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/codecamp_ecosystem.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default || true

nginx -t
systemctl restart nginx

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}✓ DEPLOYMENT SUITE INSTALLED SUCCESSFULLY!                     ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "Services Status:"
systemctl status codecampcore --no-pager -l || true
systemctl status codecamp-reg --no-pager -l || true
systemctl status attendance --no-pager -l || true

echo -e "\n${YELLOW}To activate SSL HTTPS certificates, run:${NC}"
echo -e "sudo certbot --nginx -d codecamp.com.ng -d www.codecamp.com.ng -d core.codecamp.com.ng -d attendance.codecamp.com.ng"
