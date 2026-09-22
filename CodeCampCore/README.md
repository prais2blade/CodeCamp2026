# CodeCampCore — Master Academy ERP & Portal

CodeCampCore is the central enterprise management portal for the CodeCamp Academy suite. It provides comprehensive course management, batch scheduling, student & teacher profiles, financial tracking, competition leaderboards, and serves as the master API hub for satellite applications (`Codecamp` Admissions Gateway and `attendance-system` Scanner Hub).

---

## 🏗️ The 3-Project Ecosystem

| Project | Port (Dev) | Role / Purpose |
| :--- | :--- | :--- |
| **CodeCampCore** | `http://127.0.0.1:8000` | **Master Academy ERP**: Central source of truth for students, academics, billing, and attendance aggregations. |
| **attendance-system** | `http://127.0.0.1:8001` | **Scanner & Guardian Hub**: Kiosk QR code check-in/out, live scanner, instant WhatsApp notifications. |
| **Codecamp** | `http://127.0.0.1:8002` | **Admissions Gateway**: Marketing landing page, registration funnel, payment receipt capture, auto-batching. |

Detailed architectural diagrams and SaaS scaling roadmap: [`docs/ECOSYSTEM_ARCHITECTURE.md`](file:///c:/Projects/CodeCampCore/docs/ECOSYSTEM_ARCHITECTURE.md).

---

## 🚀 Local Development Setup

### 1. CodeCampCore (Master ERP)
```bash
cd C:\Projects\CodeCampCore
venv\Scripts\activate
pip install -r requirements.txt
npm install
npm run build:css
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 2. attendance-system (Scanner & Guardian Hub)
```bash
cd C:\Projects\attendance-system\backend
attv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

### 3. Codecamp (Admissions Gateway)
```bash
cd C:\Projects\Codecamp\camp
..\cenv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8002
```

---

## 📡 REST API Endpoints (CodeCampCore)

Mounted under `/api/v1/` and protected with `X-API-KEY` or `Authorization: Bearer <token>`:

- **`POST /api/v1/enrollment/sync/`**: Ingests registrations from `Codecamp` into student accounts and courses.
- **`POST /api/v1/attendance/sync/`**: Ingests check-in/check-out logs from `attendance-system`.
- **`GET /api/v1/catalog/courses/`**: Exposes active courses and batches for dynamic registration catalogs.
- **`GET /health/`**: System health check.

---

## 🛠️ Management & Operational Commands

- **Send Payment Reminders:** `python manage.py send_payment_reminders`
- **Retry Failed Registrations (`Codecamp`):** `python manage.py retry_sync`
- **Sync Attendance Records (`attendance-system`):** `python manage.py sync_to_core --days 7`
