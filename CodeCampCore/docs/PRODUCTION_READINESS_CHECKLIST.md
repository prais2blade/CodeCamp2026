# Production Readiness Checklist: 3-System Ecosystem

This checklist provides the exact deployment procedures, security configurations, and environment requirements for putting **CodeCampCore**, **CodeCamp Summer Registration**, and **Attendance System** into production.

---

## 1. CodeCampCore (Central Academy SaaS Portal)

### 1.1 Environment Variables (`.env`)
```ini
DJANGO_SETTINGS_MODULE=core.settings.prod
SECRET_KEY=generate-a-cryptographically-secure-50-character-key
DEBUG=False
ALLOWED_HOSTS=.codecamp.org,codecampcore.yourdomain.com,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://*.codecamp.org,https://codecampcore.yourdomain.com

# PostgreSQL Database
DATABASE_URL=postgres://codecamp_user:secure_password@db-host:5432/codecamp_core_db

# Security & SSL
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Static & Media Storage
DEFAULT_FROM_EMAIL=notifications@codecamp.org
```

### 1.2 Static Files & Assets
```bash
# Compile and collect all compressed static assets
python manage.py collectstatic --noinput
```

### 1.3 WSGI Server & Process Management
```bash
# Run with Gunicorn (4 workers recommended for web traffic)
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 60
```

---

## 2. Attendance Kiosk System (Physical Hardware & Scanner App)

### 2.1 Environment Variables (`backend/.env`)
```ini
SECRET_KEY=secure-attendance-kiosk-secret-key
DEBUG=False
ALLOWED_HOSTS=attendance.yourdomain.com,127.0.0.1
CORE_API_URL=https://lagos.codecamp.org
CORE_API_KEY=cc_live_your_generated_tenant_api_key
```

### 2.2 Kiosk Offline Resilience & Network Heartbeat
- The attendance system stores scans locally in SQLite/Postgres first.
- When an internet connection is verified, scans are synced to `CodeCampCore` via the `X-API-KEY` header.

---

## 3. CodeCamp Summer Registration App

### 3.1 Environment Variables (`camp/.env`)
```ini
SECRET_KEY=secure-summer-registration-secret-key
DEBUG=False
ALLOWED_HOSTS=summer.yourdomain.com,127.0.0.1
ATTENDANCE_API_URL=https://attendance.yourdomain.com
ATTENDANCE_API_KEY=attendance-integration-key
CORE_API_URL=https://lagos.codecamp.org
CORE_API_KEY=cc_live_your_generated_tenant_api_key
```

---

## 4. Reverse Proxy & Wildcard Subdomain Routing (Nginx)

For multi-tenant SaaS subdomains (`*.codecamp.org`), configure Nginx with a wildcard server block:

```nginx
server {
    listen 443 ssl http2;
    server_name codecamp.org *.codecamp.org;

    ssl_certificate /etc/letsencrypt/live/codecamp.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/codecamp.org/privkey.pem;

    client_max_body_size 25M;

    location /static/ {
        alias /var/www/codecampcore/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/codecampcore/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
